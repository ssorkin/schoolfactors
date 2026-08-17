<script>
  import { POSTS, fmtDate } from '$lib/insights.js';
</script>

<svelte:head>
  <title>Insights — SchoolFactors</title>
  <meta
    name="description"
    content="Articles on patterns in California's statewide school data — each with the hypothesis we bring to it and the caution it deserves."
  />
</svelte:head>

<h1>Insights</h1>
<p class="lede">
  Patterns in the statewide data, published as we find them — each with the
  hypothesis we bring to it and the caution it deserves. These are correlations
  between school averages: starting points for questions, not verdicts.
</p>

<ul class="posts">
  {#each POSTS as p (p.slug)}
    <li>
      <a class="card" href="/insights/{p.slug}">
        <span class="pdate">{fmtDate(p.date)}</span>
        <span class="ptitle">{p.title}</span>
        <span class="pblurb">{p.blurb}</span>
        <span class="more">Read the analysis →</span>
      </a>
    </li>
  {/each}
</ul>

<style>
  .lede {
    font-size: 1.05rem;
    color: #4a453d;
    max-width: 46rem;
  }
  .posts {
    list-style: none;
    margin: 1.4rem 0 0;
    padding: 0;
    display: grid;
    gap: 0.9rem;
    max-width: 46rem;
  }
  .card {
    display: block;
    background: #fffdf9;
    border: 1px solid #e8e1d5;
    border-radius: 10px;
    padding: 0.9rem 1.2rem 1rem;
    text-decoration: none;
    color: inherit;
  }
  .card:hover {
    border-color: #d8c9b4;
    box-shadow: 0 4px 14px rgba(43, 39, 34, 0.07);
  }
  .pdate {
    display: block;
    color: #898781;
    font-size: 0.82rem;
  }
  .ptitle {
    display: block;
    font-size: 1.15rem;
    font-weight: 700;
    color: #211d18;
    margin: 0.15rem 0 0.3rem;
    line-height: 1.3;
  }
  .card:hover .ptitle {
    color: #b0552f;
  }
  .pblurb {
    display: block;
    color: #4a453d;
    font-size: 0.94rem;
  }
  .more {
    display: inline-block;
    margin-top: 0.5rem;
    color: #1c5cab;
    font-size: 0.88rem;
    font-weight: 600;
  }
</style>
