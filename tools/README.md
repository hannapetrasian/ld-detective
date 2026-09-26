# ld-detective verification harness

Three Playwright scripts that check the built page before a push. Run from the folder that holds `index.html` (or pass its path as the first argument).

    pip install playwright pypdf && playwright install chromium
    python3 measure.py .          # height, words, console, external requests, fonts, anchors, ids, headings, contrast, 16-width sweep, downloads, print pages
    python3 functional.py .       # reveal cards, show-all, deep link, copy buttons, skip link, mobile menu, no-JS, 200% zoom
    python3 sweep.py .            # every in-page link, every card, keyboard, toast, deep links, mobile menu, reduced motion; console watched throughout
    python3 intake.py . shots/    # the intake sheet: open, fill, save, reload, copy, clear, print only the notes, keyboard, no-JS, phone, old #open-case links
    python3 game.py .             # the main case played to the verdict at 1440 and 375; expect errors [], 5 of 6, solvedOpen true

Expected on a clean build: console [], external_requests [], broken_anchors [], dup_ids [], contrast_fails [], fonts 8, hscroll false and overflow 0 at every width, zoom200_overflow 0, errors [].

Two pitfalls: the page uses `scroll-behavior:smooth`, so any probe that scrolls must use `behavior:'instant'` or run with `reduced_motion='reduce'`; and `offsetTop` inside the CLUE articles is relative to a positioned ancestor, so use `getBoundingClientRect().top + scrollY`.
