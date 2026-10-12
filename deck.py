import random

suits = 'hearts', 'diamonds', 'clubs', 'spades'
values = 2, 3, 4, 5, 6, 7, 8, 9, 10, 'Jack', 'Queen', 'King', 'Ace'

builddeck = [(value, suit) for suit in suits for value in values]

deck = builddeck.copy()
random.shuffle(deck)

def deal_card(deck):
    return deck.pop() if deck else None