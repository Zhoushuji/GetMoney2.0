export type CountryLanguageEntry = {
  continent: string;
  country: string;
  code: string;
  languages: string[];
};

export const countryLanguageData: CountryLanguageEntry[] = [
  { continent: 'Asia', country: 'China', code: 'CN', languages: ['Chinese', 'English'] },
  { continent: 'Asia', country: 'Japan', code: 'JP', languages: ['Japanese'] },
  { continent: 'Europe', country: 'Germany', code: 'DE', languages: ['German', 'English'] },
  { continent: 'Europe', country: 'France', code: 'FR', languages: ['French', 'English'] },
  { continent: 'North America', country: 'United States', code: 'US', languages: ['English'] },
  { continent: 'South America', country: 'Brazil', code: 'BR', languages: ['Portuguese'] },
  { continent: 'Africa', country: 'South Africa', code: 'ZA', languages: ['English', 'Zulu'] },
  { continent: 'Oceania', country: 'Australia', code: 'AU', languages: ['English'] },
];
