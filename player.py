from hand import Hand


class Player:
    def __init__(self):
        self.hand = Hand()

    def __str__(self):
        return f"Player's Hand: {self.hand.cards}"


class Dealer:
    def __init__(self):
        self.hand = Hand()

    def __str__(self):
        return f"Dealer's Hand: {self.hand.cards[0]}, <hidden>"