/**
 * CAASPP student-group labels and categories. Negative IDs are complements we
 * compute from counts in the pipeline ("everyone else" for singleton groups) —
 * never by averaging percentages.
 */
export const GROUP_LABELS = {
  1: 'All students',
  3: 'Male',
  4: 'Female',
  31: 'Economically disadvantaged',
  111: 'Not econ. disadvantaged',
  160: 'English learners',
  '-160': 'Not English learners',
  8: 'Reclassified fluent (RFEP)',
  '-8': 'Not RFEP',
  170: 'Ever English learners',
  '-170': 'Never English learners',
  180: 'English only',
  128: 'With disabilities',
  99: 'No reported disabilities',
  74: 'Black or African American',
  '-74': 'Not Black',
  75: 'Amer. Indian/Alaska Native',
  '-75': 'Not Amer. Indian/AK Native',
  76: 'Asian',
  '-76': 'Not Asian',
  77: 'Filipino',
  '-77': 'Not Filipino',
  78: 'Hispanic or Latino',
  '-78': 'Not Hispanic or Latino',
  79: 'Native Hawaiian/Pacific Isl.',
  '-79': 'Not Nat. Hawaiian/Pac. Isl.',
  80: 'White',
  '-80': 'Not White',
  144: 'Two or more races',
  '-144': 'Not two or more races',
  90: 'Parents: not HS graduate',
  91: 'Parents: HS graduate',
  92: 'Parents: some college',
  93: 'Parents: college graduate',
  94: 'Parents: graduate school',
  121: 'Parents: declined to state',
  52: 'Homeless',
  53: 'Not homeless',
  240: 'Foster youth',
  241: 'Not foster youth',
  28: 'Migrant education',
  29: 'Not migrant education',
  50: 'Military family',
  51: 'Not military family'
};

export const GROUP_CATEGORIES = [
  { label: 'Economic', ids: [31, 111] },
  { label: 'Language', ids: [160, -160, 8, 170, -170, 180] },
  { label: 'Race/ethnicity', ids: [78, -78, 80, -80, 76, -76, 74, -74, 77, 144, 75, 79] },
  { label: 'Disability', ids: [128, 99] },
  { label: 'Gender', ids: [3, 4] },
  { label: 'Parent education', ids: [90, 91, 92, 93, 94, 121] },
  { label: 'Circumstances', ids: [52, 53, 240, 241, 28, 29, 50, 51] }
];

// Themed comparison rows for the default "By group" chart view: one compact
// row per theme, at most four series each. Themes with more members with data
// are chunked into consecutive rows at render time.
export const GROUP_THEMES = [
  { label: 'Economic status', ids: [31, 111] },
  { label: 'Disability', ids: [128, 99] },
  { label: 'English learners', ids: [-170, 160, 8] },
  { label: 'Race/ethnicity', ids: [78, 80, 76, 74, 77, 144, 75, 79] },
  { label: 'Parent education', ids: [90, 91, 92, 93, 94] }
];

// Compact labels for the themed-row legends.
export const GROUP_SHORT = {
  31: 'Econ disadvantaged',
  111: 'Not econ disadvantaged',
  128: 'Disabilities',
  99: 'No disabilities',
  '-170': 'Never EL',
  160: 'EL',
  8: 'RFEP',
  78: 'Hispanic',
  80: 'White',
  76: 'Asian',
  74: 'Black',
  77: 'Filipino',
  144: '2+ races',
  75: 'Am. Indian',
  79: 'Pac. Isl.',
  90: 'Not HS',
  91: 'HS grad',
  92: 'Some college',
  93: 'College grad',
  94: 'Grad school'
};

// Fixed categorical palette (validated reference palette, light mode) — assigned
// to groups in activation order, freed on deactivation, never cycled.
export const SERIES_COLORS = [
  '#2a78d6',
  '#eb6834',
  '#1baf7a',
  '#eda100',
  '#e87ba4',
  '#008300'
];
