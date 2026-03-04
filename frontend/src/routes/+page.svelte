<script lang="ts">
	import type { Apartment } from './+page.ts';

	let { data } = $props();

	let maxRent = $state('');
	let minSize = $state('');
	let minRooms = $state('');
	let sortBy = $state<'rent' | 'size_sqm' | 'rooms'>('rent');
	let sortDir = $state<'asc' | 'desc'>('asc');

	function formatRent(rent: number): string {
		return rent.toLocaleString('sv-SE') + ' kr/mån';
	}

	let filtered = $derived.by(() => {
		let result = data.apartments.filter((a: Apartment) => {
			if (maxRent && a.rent > Number(maxRent)) return false;
			if (minSize && a.size_sqm < Number(minSize)) return false;
			if (minRooms && a.rooms < Number(minRooms)) return false;
			return true;
		});

		result.sort((a: Apartment, b: Apartment) => {
			const diff = a[sortBy] - b[sortBy];
			return sortDir === 'asc' ? diff : -diff;
		});

		return result;
	});

	let rentRange = $derived.by(() => {
		const rents = data.apartments.map((a: Apartment) => a.rent);
		return { min: Math.min(...rents), max: Math.max(...rents) };
	});
</script>

<svelte:head>
	<title>Qasa Finder — Lediga lägenheter</title>
</svelte:head>

<div class="min-h-screen bg-gray-50">
	<!-- Header -->
	<header class="bg-white shadow-sm border-b border-gray-200">
		<div class="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
			<h1 class="text-2xl font-bold text-gray-900">Qasa Finder</h1>
			<p class="mt-1 text-sm text-gray-500">
				{data.apartments.length} lägenheter &middot;
				{formatRent(rentRange.min)} – {formatRent(rentRange.max)}
			</p>
		</div>
	</header>

	<main class="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
		<!-- Filters -->
		<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 items-end">
				<div>
					<label for="maxRent" class="block text-sm font-medium text-gray-700 mb-1">Max hyra (kr)</label>
					<input
						id="maxRent"
						type="number"
						bind:value={maxRent}
						placeholder="t.ex. 15000"
						class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
					/>
				</div>
				<div>
					<label for="minSize" class="block text-sm font-medium text-gray-700 mb-1">Min storlek (m²)</label>
					<input
						id="minSize"
						type="number"
						bind:value={minSize}
						placeholder="t.ex. 40"
						class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
					/>
				</div>
				<div>
					<label for="minRooms" class="block text-sm font-medium text-gray-700 mb-1">Min rum</label>
					<input
						id="minRooms"
						type="number"
						step="0.5"
						bind:value={minRooms}
						placeholder="t.ex. 2"
						class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
					/>
				</div>
				<div>
					<label for="sortBy" class="block text-sm font-medium text-gray-700 mb-1">Sortera efter</label>
					<select
						id="sortBy"
						bind:value={sortBy}
						class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
					>
						<option value="rent">Hyra</option>
						<option value="size_sqm">Storlek</option>
						<option value="rooms">Rum</option>
					</select>
				</div>
				<div>
					<label for="sortDir" class="block text-sm font-medium text-gray-700 mb-1">Ordning</label>
					<select
						id="sortDir"
						bind:value={sortDir}
						class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
					>
						<option value="asc">Lägst först</option>
						<option value="desc">Högst först</option>
					</select>
				</div>
			</div>
		</div>

		<!-- Results count -->
		<p class="text-sm text-gray-500 mb-4">
			Visar {filtered.length} av {data.apartments.length} lägenheter
		</p>

		<!-- Card grid -->
		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
			{#each filtered as apartment}
				<a
					href={apartment.link}
					target="_blank"
					rel="noopener noreferrer"
					class="block bg-white rounded-lg shadow-sm border border-gray-200 p-5 hover:shadow-md hover:border-gray-300 transition-all duration-150"
				>
					<h2 class="font-semibold text-gray-900 mb-3">{apartment.address}</h2>
					<div class="grid grid-cols-3 gap-2 text-sm">
						<div>
							<span class="text-gray-500">Hyra</span>
							<p class="font-medium text-gray-900">{formatRent(apartment.rent)}</p>
						</div>
						<div>
							<span class="text-gray-500">Storlek</span>
							<p class="font-medium text-gray-900">{apartment.size_sqm} m²</p>
						</div>
						<div>
							<span class="text-gray-500">Rum</span>
							<p class="font-medium text-gray-900">{apartment.rooms}</p>
						</div>
					</div>
					<p class="mt-3 text-xs text-blue-600">Visa på Qasa &rarr;</p>
				</a>
			{/each}
		</div>

		{#if filtered.length === 0}
			<div class="text-center py-12 text-gray-500">
				<p class="text-lg">Inga lägenheter matchar dina filter.</p>
				<p class="text-sm mt-1">Prova att ändra filtren ovan.</p>
			</div>
		{/if}
	</main>
</div>
