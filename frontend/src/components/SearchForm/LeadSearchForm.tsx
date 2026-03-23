import { FormEvent, useMemo, useState } from 'react';

import { countryLanguageData } from '../../data/countryLanguageData';

type Props = {
  onSubmit: (payload: { product_name: string; continents: string[]; countries: string[]; languages: string[]; channels: string[] }) => Promise<void>;
};

const channels = ['google', 'bing', 'facebook', 'linkedin', 'yellowpages'];

export function LeadSearchForm({ onSubmit }: Props) {
  const [productName, setProductName] = useState('industrial valve');
  const [selectedContinents, setSelectedContinents] = useState<string[]>(['Europe']);
  const [selectedCountries, setSelectedCountries] = useState<string[]>(['Germany']);
  const [selectedLanguages, setSelectedLanguages] = useState<string[]>(['German', 'English']);
  const [selectedChannels, setSelectedChannels] = useState<string[]>(channels);

  const countries = useMemo(
    () => countryLanguageData.filter((entry) => selectedContinents.length === 0 || selectedContinents.includes(entry.continent)),
    [selectedContinents],
  );

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    await onSubmit({
      product_name: productName,
      continents: selectedContinents,
      countries: selectedCountries,
      languages: selectedLanguages,
      channels: selectedChannels,
    });
  };

  return (
    <form className="panel" onSubmit={submit}>
      <h2>Lead Discovery</h2>
      <div className="form-grid">
        <label className="field">
          <span>产品名称</span>
          <input className="input" value={productName} onChange={(e) => setProductName(e.target.value)} required />
        </label>
        <label className="field">
          <span>大洲</span>
          <select className="select" multiple value={selectedContinents} onChange={(e) => setSelectedContinents(Array.from(e.target.selectedOptions).map((o) => o.value))}>
            {Array.from(new Set(countryLanguageData.map((item) => item.continent))).map((continent) => (
              <option key={continent} value={continent}>{continent}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>国家</span>
          <select
            className="select"
            multiple
            value={selectedCountries}
            onChange={(e) => {
              const nextCountries = Array.from(e.target.selectedOptions).map((o) => o.value);
              setSelectedCountries(nextCountries);
              const nextLanguages = Array.from(new Set(countries.filter((item) => nextCountries.includes(item.country)).flatMap((item) => item.languages)));
              setSelectedLanguages(nextLanguages);
            }}
          >
            {countries.map((entry) => (
              <option key={entry.code} value={entry.country}>{entry.country}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>语言</span>
          <select className="select" multiple value={selectedLanguages} onChange={(e) => setSelectedLanguages(Array.from(e.target.selectedOptions).map((o) => o.value))}>
            {Array.from(new Set(countries.flatMap((item) => item.languages))).map((language) => (
              <option key={language} value={language}>{language}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="field" style={{ marginTop: 16 }}>
        <span>搜索渠道</span>
        <div className="channel-list">
          {channels.map((channel) => (
            <label key={channel} className="tag">
              <input
                type="checkbox"
                checked={selectedChannels.includes(channel)}
                onChange={() => setSelectedChannels((current) => current.includes(channel) ? current.filter((value) => value !== channel) : [...current, channel])}
              />
              {' '}{channel}
            </label>
          ))}
        </div>
      </div>
      <div className="actions" style={{ marginTop: 20 }}>
        <button className="button" type="submit">启动异步搜索</button>
        <button className="button secondary" type="button">导出模板</button>
      </div>
    </form>
  );
}
