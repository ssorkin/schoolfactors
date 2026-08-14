<script>
  import EntityPage from '$lib/EntityPage.svelte';
  let { data } = $props();
</script>

<svelte:head><title>{data.entity.name} — SchoolFactors</title></svelte:head>

<EntityPage entity={data.entity} />
