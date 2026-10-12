import deck
from player import Player, Dealer

# Create player and dealer
player = Player()
dealer = Dealer()

for i in range(2):
    player.hand.add_card(deck.deal_card(deck.deck))
    dealer.hand.add_card(deck.deal_card(deck.deck))

# Print their hands
print(player)
print(dealer)

# Print their hand values
print("Player value:", player.hand.get_value())
print("Dealer value:", dealer.hand.get_value())

while player.hand.get_value() < 21:
    action = input("Do you want to hit or stand? (h/s): ").lower()
    if action == 'h':
        player.hand.add_card(deck.deal_card(deck.deck))
        print(player)
        print("Player value:", player.hand.get_value())
    elif action == 's':
        break
    else:
        print("Invalid input. Please enter 'h' or 's'.")


# Dealer's turn
if player.hand.get_value() <= 21:

    # Reveal the dealer's hidden card
    print("Dealer's hand:", dealer.hand.cards)
    print("Dealer value:", dealer.hand.get_value())

    # Dealer must hit until reaching at least 17
    while dealer.hand.get_value() < 17:
        dealer.hand.add_card(deck.deal_card(deck.deck))

        print("Dealer's hand:", dealer.hand.cards)
        print("Dealer value:", dealer.hand.get_value())


# Determine the winner
player_value = player.hand.get_value()
dealer_value = dealer.hand.get_value()

if player_value > 21:
    print("Player busts! Dealer wins.")
elif dealer_value > 21:
    print("Dealer busts! Player wins.")
elif player_value > dealer_value:
    print("Player wins!")
elif dealer_value > player_value:
    print("Dealer wins!")
else:
    print("It's a tie!")