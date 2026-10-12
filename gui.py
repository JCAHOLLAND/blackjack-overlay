"""Compact Tkinter blackjack overlay with bundled playing-card images."""
import math
import random
import time
import tkinter as tk
from pathlib import Path
import queue
import json
import sys
from hotkeys import GlobalHotkeys, windows_context
import deck
from hand import Hand
from player import Player, Dealer

class BlackjackOverlay:
    WIDTH, HEIGHT = 320, 410
    CLEAR = '#303236'
    SUITS = {'clubs': '♣', 'spades': '♠', 'hearts': '♥', 'diamonds': '♦'}
    RANKS = {'Jack': 'J', 'Queen': 'Q', 'King': 'K', 'Ace': 'A'}

    def __init__(self, root, enable_global=True):
        self.root = root
        self.process_context = windows_context()
        self.closing = False
        self.local_held = set()
        self.input_counts = dict.fromkeys(('Right', 'Left', 'Up', 'Down', 'Delete'), 0)
        self.last_input = None
        self.last_input_at = 0.0
        self.last_diagnostic = 0.0
        self.hotkeys = GlobalHotkeys() if enable_global else None
        root.title('Blackjack overlay')
        root.configure(bg=self.CLEAR)
        root.overrideredirect(True)
        root.attributes('-topmost', True)
        root.attributes('-alpha', 0.5)
        root.geometry(f'{self.WIDTH}x{self.HEIGHT}+{root.winfo_screenwidth()-self.WIDTH-20}+20')
        self.canvas = tk.Canvas(root, width=self.WIDTH, height=self.HEIGHT, bg=self.CLEAR, highlightthickness=0)
        self.canvas.pack()
        self.player, self.dealer = Player(), Dealer()
        self.balance, self.bet = 200, 50
        self.player.hands = [self.player.hand]
        self.player.bets = [0]
        self.active_hand_index = 0
        self.hand_stood = [False]
        self.split_aces = False
        self.phase, self.message = 'ready', 'Place your bet'
        self.shoe = []
        self.progress = self.reveal = 0.0
        self.positions = {'dealer': [], 'player_0': []}
        self.arrivals = {'dealer': [], 'player_0': []}
        self.last_frame = time.perf_counter()
        self.atlases = {}
        self.images = {}
        self.auto_job = None
        self.deadline = None
        self.bet_text = tk.StringVar(value='50')
        self.actions = {'Right': self.hit, 'Left': self.stand,
                        'Up': self.up_action, 'Down': self.down_action,
                        'Delete': self.close}
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Delete>', lambda event: self.focused_key('Delete', self.close))
        for name in self.actions:
            root.bind(f'<KeyRelease-{name}>', lambda event, key=name: self.local_held.discard(key))
        root.bind('<FocusOut>', lambda event: self.local_held.clear())
        for sequence, command in [('<Right>', self.hit), ('<Left>', self.stand),
                                  ('<Up>', self.up_action),
                                  ('<Down>', self.down_action)]:
            key = sequence[1:-1]
            root.bind(sequence, lambda event, name=key, action=command: self.focused_key(name, action))
        self.canvas.bind('<ButtonPress-1>', self.drag_start)
        self.canvas.bind('<B1-Motion>', self.drag_move)
        self.update_controls()
        self.frame()
        self.prepare_round()
        if self.hotkeys:
            self.poll_hotkeys()

    def focused_key(self, key, action):
        # Registered physical keys arrive through WM_HOTKEY, so never fire twice.
        if not self.hotkeys or key not in self.hotkeys.handled_keys:
            if key not in self.local_held:
                self.local_held.add(key)
                self.dispatch_key(key, 'focused')
        return 'break'

    def dispatch_key(self, key, source):
        before_phase, before_bet = self.phase, self.bet_text.get()
        before_hand = self.player.hand
        before_count = len(before_hand.cards)
        before_hand_index = self.active_hand_index
        before_hands = len(self.player.hands)
        before_bets = tuple(self.player.bets)
        self.input_counts[key] += 1
        self.actions[key]()
        if key == 'Up' and before_phase == 'player':
            result = 'hand split' if len(self.player.hands) > before_hands else 'split unavailable'
        elif key == 'Down' and before_phase == 'player':
            result = 'doubled down' if tuple(self.player.bets) != before_bets else 'double unavailable'
        elif key in ('Up', 'Down'):
            result = 'bet changed' if before_bet != self.bet_text.get() else 'bet locked' if before_phase not in ('betting', 'settled') else 'bet at limit'
        elif key == 'Right':
            result = 'round started' if before_phase == 'betting' and self.phase != 'betting' else 'card drawn' if len(before_hand.cards) > before_count else 'not your turn'
        elif key == 'Left':
            result = 'stood' if before_phase == 'player' and (self.phase != 'player' or self.active_hand_index != before_hand_index) else 'not your turn'
        else:
            result = 'closed'
        self.last_input = dict(key=key, source=source, result=result, phase_before=before_phase,
                               phase_after=self.phase, bet_before=before_bet,
                               bet_after=self.bet_text.get())
        self.last_input_at = time.perf_counter()
        self.write_diagnostics()

    def write_diagnostics(self):
        data = dict(build='background-input-repair', module=str(Path(__file__).resolve()),
                    process_context=self.process_context,
                    python=sys.executable, phase=self.phase,
                    input_counts=self.input_counts, last_input=self.last_input,
                    hotkeys=self.hotkeys.diagnostics() if self.hotkeys else None)
        try:
            folder = Path(__file__).resolve().parent
            for name in (f"input-diagnostics-{self.process_context['pid']}.json", 'input-diagnostics.json'):
                path = folder / name
                temporary = folder / (name+f".{self.process_context['pid']}.tmp")
                temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
                temporary.replace(path)
        except OSError:
            pass
        self.last_diagnostic = time.perf_counter()

    def poll_hotkeys(self):
        if self.closing:
            return
        while True:
            try:
                key = self.hotkeys.events.get_nowait()
            except queue.Empty:
                break
            self.dispatch_key(key, 'background')
            if self.closing:
                return
        if time.perf_counter()-self.last_diagnostic > 2:
            self.write_diagnostics()
        self.root.after(8, self.poll_hotkeys)

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.cancel_auto()
        if self.hotkeys:
            self.hotkeys.close()
        self.root.destroy()

    def key_action(self, action):
        action()
        return 'break'

    def adjust_bet(self, amount):
        if self.phase not in ('betting', 'settled') or self.balance < 1:
            return
        try:
            value = int(self.bet_text.get())
        except ValueError:
            value = self.bet
        self.bet_text.set(str(max(1, min(self.balance, value+amount))))

    def cancel_auto(self):
        if self.auto_job is not None:
            self.root.after_cancel(self.auto_job)
            self.auto_job = None
        self.deadline = None

    def schedule_deal(self, delay):
        self.cancel_auto()
        if self.balance < 1:
            self.message = 'Balance £0 · Session complete'
            self.update_controls()
            return
        self.deadline = time.perf_counter()+delay/1000
        self.auto_job = self.root.after(delay, self.auto_deal)

    def auto_deal(self):
        self.auto_job = None
        self.deadline = None
        if self.phase == 'settled':
            self.prepare_round()

    def prepare_round(self):
        self.cancel_auto()
        if self.balance < 1:
            self.phase, self.message = 'stopped', 'Balance £0 · Session complete'
            return
        try:
            wager = int(self.bet_text.get())
        except ValueError:
            wager = self.bet
        self.bet_text.set(str(max(1, min(self.balance, wager))))
        self.player.hand, self.dealer.hand = Hand(), Hand()
        self.player.hands = [self.player.hand]
        self.player.bets = [0]
        self.active_hand_index = 0
        self.hand_stood = [False]
        self.split_aces = False
        self.positions = {'dealer': [], 'player_0': []}
        self.arrivals = {'dealer': [], 'player_0': []}
        if len(self.shoe) < 16:
            self.shoe = deck.builddeck.copy()
            random.shuffle(self.shoe)
        for _ in range(2):
            self.player.hand.add_card(deck.deal_card(self.shoe))
            self.dealer.hand.add_card(deck.deal_card(self.shoe))
        self.progress = self.reveal = 0.0
        self.phase, self.message = 'betting', 'Choose your bet'

    def drag_start(self, event):
        self.drag_offset = (event.x_root-self.root.winfo_x(), event.y_root-self.root.winfo_y())

    def drag_move(self, event):
        if hasattr(self, 'drag_offset'):
            self.root.geometry(f'+{event.x_root-self.drag_offset[0]}+{event.y_root-self.drag_offset[1]}')

    def draw_card(self, x, y, width, height, card, face=True, flip=None):
        rank, suit = card
        name = f'{str(rank).lower()}_of_{suit}' if face else 'back'
        if isinstance(flip, tuple):
            slot = (61 if height >= 74 else 92)+round(flip[0]*30)
        else:
            slot = max(0, min(29, round(height)-59)) if flip is None else 30+round(flip*30)
        key = (name, slot)
        if key not in self.images:
            if name not in self.atlases:
                path = Path(__file__).resolve().parent / 'assets' / 'cards' / (name+'.png')
                self.atlases[name] = tk.PhotoImage(master=self.root, file=str(path))
            image = tk.PhotoImage(master=self.root, width=64, height=88)
            self.root.tk.call(str(image), 'copy', str(self.atlases[name]), '-from',
                              0, slot*88, 64, (slot+1)*88, '-to', 0, 0)
            self.images[key] = image
        self.canvas.create_image(x, y, image=self.images[key], tags='scene')

    def frame(self):
        now = time.perf_counter()
        dt = min(now-self.last_frame, .05)
        self.last_frame = now
        target = 1.0 if self.phase in ('dealer', 'settled') else 0.0
        self.progress += max(-dt/.36, min(dt/.36, target-self.progress))
        self.reveal += max(-dt/.44, min(dt/.44, target-self.reveal))
        t = self.progress*self.progress*(3-2*self.progress)
        self.canvas.delete('scene')
        text = self.canvas.create_text
        text(12, 25, anchor='w', text=f'Balance  £{self.balance:,.0f}', fill='#eeeeec', font=('Segoe UI', 11), tags='scene')
        text(199, 25, anchor='e', text='Bet £', fill='#b5b5b3', font=('Segoe UI', 10), tags='scene')
        text(232, 25, text=self.bet_text.get(), fill='#eeeeec', font=('Segoe UI', 11), tags='scene')
        rows = [('dealer', self.dealer.hand, 104, 59+29*t, False)]
        if len(self.player.hands) == 1:
            rows.append(('player_0', self.player.hands[0], 225, 88-29*t, True))
        else:
            hand_height = 72-18*t
            rows.extend((f'player_{index}', hand, y, hand_height, True)
                        for index, (hand, y) in enumerate(zip(self.player.hands, (202, 285))))
        for name, hand, y, height, is_player in rows:
            hidden = name == 'dealer' and self.reveal < .5
            betting = self.phase == 'betting'
            total = '—'
            if hand.cards:
                if betting:
                    total = '?'
                elif hidden:
                    visible = Hand()
                    visible.add_card(hand.cards[0])
                    total = f'{visible.get_value()} + ?'
                else:
                    total = str(hand.get_value())
            if is_player and len(self.player.hands) > 1:
                index = int(name.rsplit('_', 1)[1])
                label = f'Hand {index+1}' + (' ·' if index == self.active_hand_index and self.phase == 'player' else '')
                text(12, y-height/2-13, anchor='w', text=label, fill='#b5b5b3',
                     font=('Segoe UI', 9), tags='scene')
                text(306, y-height/2-13, anchor='e', text=f'Bet £{self.player.bets[index]}',
                     fill='#b5b5b3', font=('Segoe UI', 9), tags='scene')
            else:
                text(12, y-height/2-13, anchor='w', text='Player' if is_player else 'Dealer',
                     fill='#b5b5b3', font=('Segoe UI', 9), tags='scene')
            total_x = 270 if is_player and len(self.player.hands) > 1 else 306
            text(total_x, y-height/2-13, anchor='e', text=total, fill='#eeeeec',
                 font=('Segoe UI', 11), tags='scene')
            width = height*5/7
            count = len(hand.cards)
            spacing = min(width+9, (284-width)/max(1, count-1))
            start = 160-(width+(count-1)*spacing)/2+width/2
            positions = self.positions[name]
            for i, card in enumerate(hand.cards):
                dest = start+i*spacing
                if i >= len(positions):
                    positions.append([min(302-width/2, dest+28), y+8])
                    self.arrivals[name].append(now)
                positions[i][0] += (dest-positions[i][0])*(1-math.exp(-dt*15))
                positions[i][1] += (y-positions[i][1])*(1-math.exp(-dt*15))
                face, flip = True, None
                if betting:
                    face, flip = False, None
                elif name == 'dealer' and i == 1:
                    face = self.reveal >= .5
                    flip = self.reveal
                elif i < len(self.arrivals[name]):
                    arrival = min(1.0, (now-self.arrivals[name][i])/.32)
                    if arrival < 1:
                        face, flip = arrival >= .5, (arrival,)
                self.draw_card(*positions[i], width, height, card, face, flip)
        message = self.message
        if self.deadline is not None:
            message += f' · Next hand in {max(1, math.ceil(self.deadline-time.perf_counter()))}s'
        text(160, 337, text=message, fill='#eeeeec', font=('Segoe UI', 10), tags='scene')
        hint = '↑ ↓ Bet £10  ·  → Start' if self.phase == 'betting' else '← Stand  ·  Hit →'
        if self.phase == 'player':
            hint = '← Stand  ·  → Hit  ·  ↑ Split  ·  ↓ Double'
        if self.phase == 'settled':
            hint = '↑ ↓ Next bet £10'
        elif self.phase in ('dealer', 'stopped'):
            hint = ''
        text(160, 366, text=hint, fill='#eeeeec', font=('Segoe UI', 9), tags='scene')
        scope = 'Click overlay for keys'
        if self.hotkeys:
            if not self.hotkeys.ready.is_set():
                scope = 'Starting background keys'
            elif len(self.hotkeys.handled_keys) == len(self.actions):
                scope = 'Background keys: filter' if self.hotkeys.hooked else 'Global game keys'
            else:
                missing = ', '.join(key for key in self.actions if key not in self.hotkeys.handled_keys)
                scope = f'Click for: {missing}'
        if self.last_input and time.perf_counter()-self.last_input_at < 2:
            scope = self.last_input['key']+': '+self.last_input['result']
        text(160, 394, text=scope+' · Del close', fill='#b5b5b3', font=('Segoe UI', 8), tags='scene')
        self.canvas.tag_lower('scene')
        self.root.after(16, self.frame)

    def update_controls(self):
        # All controls are keyboard actions, gated by their handlers.
        pass

    def start_round(self):
        if self.phase != 'betting':
            return
        try:
            wager = int(self.bet_text.get())
        except ValueError:
            self.message = 'Choose a valid bet'
            return
        if not 1 <= wager <= self.balance:
            self.message = 'Bet must be £1 up to your balance'
            return
        self.bet = wager
        self.balance -= wager
        self.player.bets = [wager]
        self.hand_stood = [False]
        self.active_hand_index = 0
        self.player.hands = [self.player.hand]
        now = time.perf_counter()
        self.arrivals = {'dealer': [now]*2, 'player_0': [now]*2}
        self.phase, self.message = 'player', 'Your turn'
        if self.player.hand.get_value() == 21:
            self.stand()

    def hit(self):
        if self.phase == 'betting':
            self.start_round()
            return
        if self.phase != 'player':
            return
        self.player.hand.add_card(deck.deal_card(self.shoe))
        if self.player.hand.get_value() >= 21:
            self.hand_stood[self.active_hand_index] = True
            self.advance_hand()

    def down_action(self):
        if self.phase == 'player':
            self.double_down()
        else:
            self.adjust_bet(-10)

    def up_action(self):
        if self.phase == 'player':
            self.split()
        else:
            self.adjust_bet(10)

    def split(self):
        if self.phase != 'player' or len(self.player.hands) != 1:
            return
        hand = self.player.hand
        if len(hand.cards) != 2 or hand.cards[0][0] != hand.cards[1][0]:
            self.message = 'Split requires a matching pair'
            return
        wager = self.player.bets[self.active_hand_index]
        if self.balance < wager:
            self.message = 'Not enough balance to split'
            return
        first, second = hand.cards
        self.balance -= wager
        self.player.hands = [Hand(), Hand()]
        self.player.hands[0].add_card(first)
        self.player.hands[1].add_card(second)
        self.player.bets = [wager, wager]
        self.hand_stood = [False, False]
        self.active_hand_index = 0
        self.player.hand = self.player.hands[0]
        self.positions['player_0'] = []
        self.positions['player_1'] = []
        self.arrivals['player_0'] = []
        self.arrivals['player_1'] = []
        self.split_aces = first[0] == 'Ace'
        for index, split_hand in enumerate(self.player.hands):
            split_hand.add_card(deck.deal_card(self.shoe))
            if split_hand.get_value() >= 21:
                self.hand_stood[index] = True
        if self.split_aces:
            self.hand_stood = [True, True]
            self.message = 'Split aces · one card each'
            self.advance_hand()
        elif self.hand_stood[0]:
            self.advance_hand()
        else:
            self.message = 'Your turn · Hand 1'

    def double_down(self):
        if self.phase != 'player':
            return
        hand = self.player.hand
        index = self.active_hand_index
        wager = self.player.bets[index]
        if self.split_aces or len(hand.cards) != 2:
            self.message = 'Double down unavailable'
            return
        if self.balance < wager:
            self.message = 'Not enough balance to double'
            return
        self.balance -= wager
        self.player.bets[index] += wager
        hand.add_card(deck.deal_card(self.shoe))
        self.hand_stood[index] = True
        self.message = f'Hand {index+1} doubled down'
        self.advance_hand()

    def advance_hand(self):
        for index in range(self.active_hand_index+1, len(self.player.hands)):
            if not self.hand_stood[index]:
                self.active_hand_index = index
                self.player.hand = self.player.hands[index]
                self.message = f'Your turn · Hand {index+1}'
                return
        self.phase, self.message = 'dealer', 'Dealer’s turn'
        self.update_controls()
        self.root.after(550, self.dealer_step)

    def stand(self):
        if self.phase != 'player':
            return
        self.hand_stood[self.active_hand_index] = True
        self.advance_hand()

    def dealer_step(self):
        if self.phase != 'dealer':
            return
        if any(hand.get_value() <= 21 for hand in self.player.hands) and self.dealer.hand.get_value() < 17:
            self.dealer.hand.add_card(deck.deal_card(self.shoe))
            self.root.after(650, self.dealer_step)
            return
        dealer_total = self.dealer.hand.get_value()
        results = []
        for index, hand in enumerate(self.player.hands):
            player_total = hand.get_value()
            wager = self.player.bets[index]
            if player_total > 21:
                result = 'bust'
            elif dealer_total > 21 or player_total > dealer_total:
                self.balance += 2*wager
                result = 'win'
            elif player_total == dealer_total:
                self.balance += wager
                result = 'push'
            else:
                result = 'lose'
            results.append(result)
        if len(results) == 1:
            result = results[0]
            if result == 'bust':
                self.message = 'You bust · Dealer wins'
            elif result == 'win':
                self.message = 'Dealer busts · You win' if dealer_total > 21 else 'You win'
            elif result == 'push':
                self.message = 'Push · Bet returned'
            else:
                self.message = 'Dealer wins'
        else:
            self.message = ' · '.join(f'Hand {index+1}: {result}'
                                      for index, result in enumerate(results))
        self.phase = 'settled'
        self.bet_text.set(str(min(self.bet, self.balance) if self.balance > 0 else self.bet))
        self.update_controls()
        self.schedule_deal(4000)

def main():
    root = tk.Tk()
    BlackjackOverlay(root)
    root.mainloop()

if __name__ == '__main__':
    main()
