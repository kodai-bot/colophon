# SPDX-License-Identifier: AGPL-3.0-or-later
"""
quotes.py - Rotating footer quotes for the Yeats Society Bookshop counter.

A quiet manifesto. For the staff. Against entropy.
"""

import random

QUOTES = [
    # Yeats
    ("Things fall apart; the centre cannot hold.", "W.B. Yeats"),
    ("I have spread my dreams under your feet; tread softly.", "W.B. Yeats"),
    ("Think like a wise man but communicate in the language of the people.", "W.B. Yeats"),
    ("Education is not the filling of a pail, but the lighting of a fire.", "W.B. Yeats"),
    ("In dreams begins responsibility.", "W.B. Yeats"),
    ("Do not wait to strike till the iron is hot; make it hot by striking.", "W.B. Yeats"),
    ("The world is full of magic things, patiently waiting for our senses to grow sharper.", "W.B. Yeats"),
    ("The best lack all conviction, while the worst are full of passionate intensity.", "W.B. Yeats"),
    ("Out of the quarrel with others we make rhetoric; out of the quarrel with ourselves we make poetry.", "W.B. Yeats"),
    ("How can we know the dancer from the dance?", "W.B. Yeats"),
    ("All changed, changed utterly: a terrible beauty is born.", "W.B. Yeats"),
    ("Too long a sacrifice can make a stone of the heart.", "W.B. Yeats"),

    # Spock / Star Trek
    ("The needs of the many outweigh the needs of the few.", "Spock"),
    ("Insufficient facts always invite danger.", "Spock"),
    ("Logic is the beginning of wisdom, not the end.", "Spock"),
    ("Without followers, evil cannot spread.", "Spock"),
    ("Computers make excellent and efficient servants, but I have no wish to serve under them.", "Spock"),
    ("Change is the essential process of all existence.", "Spock"),
    ("Live long and prosper.", "Spock"),
    ("Curious how often you humans manage to obtain that which you do not want.", "Spock"),

    # The Rebel Alliance
    ("A rebellion is built on hope.", "Jyn Erso, Rogue One"),
    ("rebellions are built on hope.", "Cassian Andor, Rogue One"),
    ("We are the spark that will light the fire that'll burn the Empire down.", "Ezra Bridger"),
    ("Never tell me the odds.", "Han Solo"),
    ("Do. Or do not. There is no try.", "Yoda"),
    ("Fear leads to anger. Anger leads to hate. Hate leads to suffering.", "Yoda"),
    ("So this is how liberty dies — with thunderous applause.", "Padmé Amidala"),
    ("Hope is like the sun. If you only believe it when you see it, you'll never make it through the night.", "Rose Tico, The Last Jedi"),

    # Data & Information
    ("Without data you're just another person with an opinion.", "W. Edwards Deming"),
    ("Information wants to be free.", "Stewart Brand"),
    ("In God we trust; all others must bring data.", "W. Edwards Deming"),
    ("The goal is to turn data into information, and information into insight.", "Carly Fiorina"),
    ("What gets measured gets managed.", "Peter Drucker"),
    ("Data is not information, information is not knowledge, knowledge is not understanding, understanding is not wisdom.", "Clifford Stoll"),
    ("Errors using inadequate data are much less than those using no data at all.", "Charles Babbage"),

    # Logic & Necessity
    ("The truth will set you free, but first it will make you miserable.", "James A. Garfield"),
    ("Any sufficiently advanced bureaucracy is indistinguishable from paralysis.", "Unknown"),
    ("The measure of intelligence is the ability to change.", "Albert Einstein"),
    ("Insanity is doing the same thing over and over and expecting different results.", "Albert Einstein"),
    ("Not everything that can be counted counts, and not everything that counts can be counted.", "Albert Einstein"),
    ("It is not that I'm so smart, it's just that I stay with problems longer.", "Albert Einstein"),
    ("We cannot solve our problems with the same thinking we used when we created them.", "Albert Einstein"),
    ("Prediction is very difficult, especially if it's about the future.", "Niels Bohr"),

    # For the staff, quietly
    ("First, do no harm. Second, do not leave things as you found them if you can improve them.", "Unknown"),
    ("The most dangerous phrase in the language is: we've always done it this way.", "Grace Hopper"),
    ("One machine can do the work of fifty ordinary men. No machine can do the work of one extraordinary man.", "Elbert Hubbard"),
    ("The best tool is the one that helps the person doing the work.", "Unknown"),
    ("Do the best you can until you know better. Then when you know better, do better.", "Maya Angelou"),
    ("Well done is better than well said.", "Benjamin Franklin"),
    ("If I have seen further it is by standing on the shoulders of Giants.", "Isaac Newton"),
    ("Small deeds done are better than great deeds planned.", "Peter Marshall"),

    # Oscar Wilde — art, socialism, the examined life
    ("A map of the world that does not include Utopia is not worth even glancing at.", "Oscar Wilde"),
    ("Disobedience, in the eyes of anyone who has read history, is man's original virtue.", "Oscar Wilde"),
    ("Art is the most intense mode of individualism that the world has known.", "Oscar Wilde"),
    ("Society often forgives the criminal; it never forgives the dreamer.", "Oscar Wilde"),
    ("The books that the world calls immoral are books that show the world its own shame.", "Oscar Wilde"),
    ("To live is the rarest thing in the world. Most people exist, that is all.", "Oscar Wilde"),
    ("A man who does not think for himself does not think at all.", "Oscar Wilde"),
    ("We are all in the gutter, but some of us are looking at the stars.", "Oscar Wilde"),
    ("I can resist everything except temptation.", "Oscar Wilde"),
    ("The truth is rarely pure and never simple.", "Oscar Wilde"),
    ("We are each our own devil, and we make this world our hell.", "Oscar Wilde"),

    # William Morris — art, labour, fellowship
    ("Have nothing in your houses that you do not know to be useful or believe to be beautiful.", "William Morris"),
    ("I do not want art for a few, any more than education for a few, or freedom for a few.", "William Morris"),
    ("Fellowship is life, and lack of fellowship is death.", "William Morris"),
    ("The reward of labour is life. Is that not enough?", "William Morris"),
    ("Men fight and lose the battle, and the thing that they fought for comes about in spite of their defeat.", "William Morris"),
    ("Art is man's expression of his joy in labour.", "William Morris"),

    # Anarchist & kindred spirits
    ("No great idea in its beginning can ever be within the law.", "Emma Goldman"),
    ("If I can't dance, I don't want to be part of your revolution.", "Emma Goldman"),
    ("The future belongs to those who can imagine it, and the present belongs to those brave enough to live it.", "Unknown"),
    ("Ask for work. If they don't give you work, ask for bread. If they do not give you work or bread, then take bread.", "Emma Goldman"),
    ("The most violent element in society is ignorance.", "Emma Goldman"),

    # Star Trek — utopian ideals (Picard, Data, and beyond)
    ("The acquisition of wealth is no longer the driving force in our lives. We work to better ourselves and the rest of humanity.", "Captain Picard"),
    ("With the first link, the chain is forged. The first speech censured, the first thought forbidden, the first freedom denied chains us all irrevocably.", "Captain Picard"),
    ("Things are only impossible until they're not.", "Captain Picard"),
    ("It is the struggle itself that is most important. We must strive to be more than we are.", "Data, TNG"),
    ("You cannot explain away a wantonly cruel act by pointing to books and saying they made me do it.", "Captain Picard"),
    ("When one has been threatened with a great injustice, one accepts a smaller as a favour.", "Captain Picard"),
    ("Compassion: that's the one thing no machine ever had. Maybe it's the one thing that keeps men ahead of them.", "Dr. Leonard McCoy"),
    ("Risk is our business. That's what the starship is all about.", "Captain Kirk"),
    ("The line must be drawn here! This far, no further!", "Captain Picard"),

    # Irish literary — Yeats and Beckett's kindred voices
    ("Ever tried. Ever failed. No matter. Try again. Fail again. Fail better.", "Samuel Beckett"),
    ("I can't go on. I'll go on.", "Samuel Beckett"),
    ("Nothing is funnier than unhappiness.", "Samuel Beckett"),
    ("Mistakes are the portals of discovery.", "James Joyce"),
    ("Think you're escaping and run into yourself. Longest way round is the shortest way home.", "James Joyce"),
    ("Walk on air against your better judgement.", "Seamus Heaney"),
    ("History says, don't hope on this side of the grave, but then, once in a lifetime the longed-for tidal wave of justice can rise up, and hope and history rhyme.", "Seamus Heaney"),

    # Books & Libraries
    ("A room without books is like a body without a soul.", "Cicero"),
    ("There is no friend as loyal as a book.", "Ernest Hemingway"),
    ("I have always imagined that Paradise will be a kind of library.", "Jorge Luis Borges"),
    ("A book is a dream that you hold in your hand.", "Neil Gaiman"),
]


def get_random_quote() -> tuple[str, str]:
    """Return a random (quote, attribution) tuple."""
    return random.choice(QUOTES)


def get_quote_display() -> str:
    """Return a formatted quote string for the footer."""
    text, author = get_random_quote()
    return f'"{text}" — {author}'


def get_all_quotes() -> list[tuple[str, str]]:
    """Return all quotes — useful for cycling through them."""
    return QUOTES.copy()
