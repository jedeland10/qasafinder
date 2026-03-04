export async function load({ fetch }) {
	const res = await fetch('/apartments.json');
	const apartments: Apartment[] = await res.json();
	return { apartments };
}

export interface Apartment {
	rent: number;
	size_sqm: number;
	rooms: number;
	address: string;
	link: string;
}
