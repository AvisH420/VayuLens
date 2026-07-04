// Target cities. Delhi for data richness, Panaji as the clean-air contrast
// (per the work-allocation doc: "Delhi + a contrast city of your choice").
// Ward seeds double as pollution hotspots for the mock field; `kind` biases
// which source dominates around that seed.

export const CITIES = {
  delhi: {
    id: "delhi",
    name: "Delhi",
    center: [77.16, 28.61],
    zoom: 9.9,
    bbox: { latMin: 28.42, latMax: 28.82, lonMin: 76.92, lonMax: 77.38 },
    latStep: 0.011,
    lonStep: 0.0125,
    baseAqi: 210,
    wind: { speed: 2.3, dir: 300 },
    stations: 40,
    wards: [
      { name: "Anand Vihar", lat: 28.647, lon: 77.316, kind: "traffic", amp: 150 },
      { name: "Wazirpur", lat: 28.7, lon: 77.165, kind: "industry", amp: 120 },
      { name: "Okhla", lat: 28.535, lon: 77.28, kind: "industry", amp: 110 },
      { name: "Dwarka", lat: 28.58, lon: 77.045, kind: "construction", amp: 95 },
      { name: "Rohini", lat: 28.74, lon: 77.09, kind: "construction", amp: 80 },
      { name: "Narela", lat: 28.8, lon: 77.09, kind: "burning", amp: 105 },
      { name: "Mundka", lat: 28.68, lon: 77.03, kind: "industry", amp: 100 },
      { name: "Jahangirpuri", lat: 28.73, lon: 77.17, kind: "burning", amp: 90 },
      { name: "Punjabi Bagh", lat: 28.67, lon: 77.13, kind: "traffic", amp: 85 },
      { name: "Chandni Chowk", lat: 28.656, lon: 77.23, kind: "traffic", amp: 75 },
      { name: "RK Puram", lat: 28.565, lon: 77.175, kind: "traffic", amp: 60 },
      { name: "Patparganj", lat: 28.62, lon: 77.29, kind: "construction", amp: 70 },
      { name: "Najafgarh", lat: 28.61, lon: 76.98, kind: "dust", amp: 80 },
      { name: "Shahdara", lat: 28.69, lon: 77.29, kind: "traffic", amp: 78 },
    ],
  },
  panaji: {
    id: "panaji",
    name: "Panaji",
    center: [73.83, 15.49],
    zoom: 11.8,
    bbox: { latMin: 15.42, latMax: 15.56, lonMin: 73.76, lonMax: 73.9 },
    latStep: 0.011,
    lonStep: 0.0117,
    baseAqi: 52,
    wind: { speed: 4.1, dir: 250 },
    stations: 3,
    wards: [
      { name: "Panaji Centre", lat: 15.496, lon: 73.828, kind: "traffic", amp: 26 },
      { name: "Ribandar", lat: 15.5, lon: 73.86, kind: "dust", amp: 14 },
      { name: "Taleigao", lat: 15.464, lon: 73.822, kind: "construction", amp: 20 },
      { name: "Dona Paula", lat: 15.457, lon: 73.803, kind: "traffic", amp: 10 },
      { name: "Miramar", lat: 15.48, lon: 73.81, kind: "traffic", amp: 12 },
      { name: "St. Cruz", lat: 15.49, lon: 73.86, kind: "burning", amp: 16 },
      { name: "Bambolim", lat: 15.46, lon: 73.86, kind: "construction", amp: 14 },
      { name: "Porvorim", lat: 15.53, lon: 73.82, kind: "construction", amp: 18 },
    ],
  },
};

export const DEFAULT_CITY = "delhi";
