# Icons

`lucide.json` holds [Lucide](https://lucide.dev) 1.77.0, 2,410 line icons, as one map from an icon's name to the markup inside its 24×24 `<svg>`. `./fw deck-compile` reads it for the `icons:` slot and writes the chosen icons into the slide, so a deck carries only the icons it uses and no icon file. `./fw deck-compile --icons <keyword>` lists the names that contain a word.

Lucide is under the ISC licence, and the icons it took from Feather under MIT; both texts are in [`LICENSE-lucide`](LICENSE-lucide), which must stay beside the data.

To update: download the `lucide-static` package's tarball from the npm registry, and for each `icons/<name>.svg` keep what is between `<svg …>` and `</svg>` with runs of whitespace collapsed. Check that the result holds only drawing elements (`path`, `circle`, `rect`, `line`, `polyline`, `polygon`, `ellipse`); `tests/test_deck_content.py` holds the file to that. Copy the package's `LICENSE` over `LICENSE-lucide`, and change the version here and in `deck-svg/SKILL.md`.
