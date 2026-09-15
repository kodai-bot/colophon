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

    # Spock / Star Trek
    ("The needs of the many outweigh the needs of the few.", "Spock"),
    ("Insufficient facts always invite danger.", "Spock"),
    ("Logic is the beginning of wisdom, not the end.", "Spock"),
    ("Without followers, evil cannot spread.", "Spock"),
    ("Computers make excellent and efficient servants, but I have no wish to serve under them.", "Spock"),
    ("Change is the essential process of all existence.", "Spock"),

    # The Rebel Alliance
    ("A rebellion is built on hope.", "Jyn Erso, Rogue One"),
    ("rebellions are built on hope.", "Cassian Andor, Rogue One"),
    ("We are the spark that will light the fire that'll burn the Empire down.", "Ezra Bridger"),
    ("Never tell me the odds.", "Han Solo"),

    # Data & Information
    ("Without data you're just another person with an opinion.", "W. Edwards Deming"),
    ("Information wants to be free.", "Stewart Brand"),
    ("In God we trust; all others must bring data.", "W. Edwards Deming"),
    ("The goal is to turn data into information, and information into insight.", "Carly Fiorina"),
    ("What gets measured gets managed.", "Peter Drucker"),

    # Logic & Necessity
    ("The truth will set you free, but first it will make you miserable.", "James A. Garfield"),
    ("Any sufficiently advanced bureaucracy is indistinguishable from paralysis.", "Unknown"),
    ("The measure of intelligence is the ability to change.", "Albert Einstein"),
    ("Insanity is doing the same thing over and over and expecting different results.", "Albert Einstein"),
    ("Not everything that can be counted counts, and not everything that counts can be counted.", "Albert Einstein"),

    # For the staff, quietly
    ("First, do no harm. Second, do not leave things as you found them if you can improve them.", "Unknown"),
    ("The most dangerous phrase in the language is: we've always done it this way.", "Grace Hopper"),
    ("One machine can do the work of fifty ordinary men. No machine can do the work of one extraordinary man.", "Elbert Hubbard"),
    ("The best tool is the one that helps the person doing the work.", "Unknown"),

    # Oscar Wilde — art, socialism, the examined life
    ("A map of the world that does not include Utopia is not worth even glancing at.", "Oscar Wilde"),
    ("Disobedience, in the eyes of anyone who has read history, is man's original virtue.", "Oscar Wilde"),
    ("Art is the most intense mode of individualism that the world has known.", "Oscar Wilde"),
    ("Society often forgives the criminal; it never forgives the dreamer.", "Oscar Wilde"),
    ("The books that the world calls immoral are books that show the world its own shame.", "Oscar Wilde"),
    ("To live is the rarest thing in the world. Most people exist, that is all.", "Oscar Wilde"),
    ("A man who does not think for himself does not think at all.", "Oscar Wilde"),

    # William Morris — art, labour, fellowship
    ("Have nothing in your houses that you do not know to be useful or believe to be beautiful.", "William Morris"),
    ("I do not want art for a few, any more than education for a few, or freedom for a few.", "William Morris"),
    ("Fellowship is life, and lack of fellowship is death.", "William Morris"),
    ("The reward of labour is life. Is that not enough?", "William Morris"),
    ("Men fight and lose the battle, and the thing that they fought for comes about in spite of their defeat.", "William Morris"),

    # Anarchist & kindred spirits
    ("No great idea in its beginning can ever be within the law.", "Emma Goldman"),
    ("If I can't dance, I don't want to be part of your revolution.", "Emma Goldman"),
    ("The future belongs to those who can imagine it, and the present belongs to those brave enough to live it.", "Unknown"),

    # Star Trek — utopian ideals (Picard, Data, and beyond)
    ("The acquisition of wealth is no longer the driving force in our lives. We work to better ourselves and the rest of humanity.", "Captain Picard"),
    ("With the first link, the chain is forged. The first speech censured, the first thought forbidden, the first freedom denied chains us all irrevocably.", "Captain Picard"),
    ("Things are only impossible until they're not.", "Captain Picard"),
    ("It is the struggle itself that is most important. We must strive to be more than we are.", "Data, TNG"),
    ("You cannot explain away a wantonly cruel act by pointing to books and saying they made me do it.", "Captain Picard"),
    ("When one has been threatened with a great injustice, one accepts a smaller as a favour.", "Captain Picard"),

    # Irish literary — Beckett fits here in spirit
    ("Ever tried. Ever failed. No matter. Try again. Fail again. Fail better.", "Samuel Beckett"),
    ("I can't go on. I'll go on.", "Samuel Beckett"),
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
