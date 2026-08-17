<script>
  import EntityPage from '$lib/EntityPage.svelte';
  let { data } = $props();
</script>

<EntityPage
  entity={data.entity}
  subItems={data.schools}
  subKind="school"
  subLabel="Schools in this district"
/>
