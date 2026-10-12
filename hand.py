class Hand:
    def __init__(self):
        self.cards = []

    def add_card(self, card):
        self.cards.append(card)

    def get_value(self):
        value = 0
        aces = 0

        for card in self.cards:
            if isinstance(card[0], int):
                value += card[0]

            elif card[0] in ["Jack", "Queen", "King"]:
                value += 10

            else:
                value += 11
                aces += 1

        while value > 21 and aces > 0:
            value -= 10
            aces -= 1

        return value