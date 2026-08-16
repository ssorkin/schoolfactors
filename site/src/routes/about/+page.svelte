<svelte:head><title>About — SchoolFactors</title></svelte:head>

<h1>About SchoolFactors</h1>

<p>
  SchoolFactors is an independent, open-source analysis of California's public
  education data. Every number on the site is computed from public CDE and CAASPP
  files by a <a href="https://github.com/ssorkin/schoolfactors">published pipeline</a>
  anyone can run — acquisition, cleaning, modeling, and the site itself. The project
  exists because raw test scores mostly measure who a school serves, not what it
  contributes, and because the tools that try to correct for that have historically
  either oversimplified (single composite ratings, bare ranks) or overclaimed
  (causal language on correlational data). We aim for the narrow honest lane in
  between: careful adjustment, visible uncertainty, documented data problems, and
  <a href="/methodology">no causal claims</a>.
</p>

<h2>Who's behind it</h2>

<p>
  SchoolFactors is built by
  <a href="https://www.linkedin.com/in/stephensorkin/">Stephen Sorkin</a>. Stephen
  holds a BS in Computer Science with honors and distinction from Stanford and an MS
  in Computer Science from UC Berkeley (ABD for the PhD). He was an early employee
  and executive at Splunk, working on making large messy datasets searchable and
  useful — the same problem this site tackles with public education data.
</p>

<p>
  On the education side: Stephen taught for a year at a public high school
  (engineering and geometry), and served on the board of the Sonoma Valley Education
  Foundation from 2020 to 2023.
</p>

<h2>Contact and contributions</h2>

<p>
  The data pipeline, analysis decisions, and
  <a href="/data">known data issues</a> are all in the open on
  <a href="https://github.com/ssorkin/schoolfactors">GitHub</a> — corrections,
  issues, and pull requests are welcome. If you spot a number that looks wrong,
  please say so; finding and documenting data problems is half the project.
</p>

<style>
  p {
    max-width: 46rem;
  }
  h2 {
    margin-top: 2rem;
  }
</style>
