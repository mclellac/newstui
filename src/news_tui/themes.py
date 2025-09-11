from __future__ import annotations

from textual.theme import Theme

THEMES = {
    "adwaita-dark": Theme(
        name="adwaita-dark",
        primary="#303030",
        accent="#3584e4",
        foreground="#eeeeec",
        background="#242424",
        dark=True,
    ),
    "adwaita-light": Theme(
        name="adwaita-light",
        primary="#ebebeb",
        accent="#3584e4",
        foreground="#3d3d3d",
        background="#fafafa",
        dark=False,
    ),
    "dracula": Theme(
        name="dracula",
        primary="#44475a",
        accent="#bd93f9",
        foreground="#f8f8f2",
        background="#282a36",
        dark=True,
    ),
    "nord": Theme(
        name="nord",
        primary="#434c5e",
        accent="#88c0d0",
        foreground="#d8dee9",
        background="#2e3440",
        dark=True,
    ),
    "osaka-jade": Theme(
        name="osaka-jade",
        primary="#003f4a",
        accent="#2aa198",
        foreground="#93a1a1",
        background="#002731",
        dark=True,
    ),
    "rosepine": Theme(
        name="rosepine",
        primary="#31748f",
        accent="#eb6f92",
        foreground="#e0def4",
        background="#191724",
        dark=True,
    ),
}
