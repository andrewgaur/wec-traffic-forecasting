# WEC Traffic Forecasting demo

Open `index.html` in a browser. It needs no build step, package install or server. Public Sans is included locally with its Open Font License in `assets/fonts`.

Pick a Hypercar and completed lap to inspect the latest available observations and a median recent pace baseline. Use “Reveal next lap” to compare the estimate with the synthetic outcome. Moving the origin hides the outcome again. The sequence withholds future times, and the chart's scale uses only completed laps and the estimate.

The data formula and scripted delays come from the original public demo. This interface demonstrates forecast origins. It does not execute the Python pipeline or claim a trained traffic model or real race performance.

`styles.css` contains the responsive design. `demo.js` contains the invented race and interface calculations. Taste skill direction notes and browser checks live in `.taste-skill`, which is for local review and is not needed on the public site.

To publish with GitHub Pages, put `index.html`, `styles.css`, `demo.js`, `.nojekyll` and `assets/` at the root of the existing `gh-pages` branch. Exclude `.taste-skill/`. The Pages source is that branch's root. The public URL is `https://andrewgaur.github.io/wec-traffic-forecasting/`.
