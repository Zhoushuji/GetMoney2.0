import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useRef } from 'react';

import { CONTINENTS, LANGUAGE_LABELS, geoData } from '../../data/geo';

export type LeadSearchPayload = {
  product_name: string;
  continents: string[];
  countries: string[];
  languages: string[];
  target_count: number | null;
  mode: 'live' | 'demo';
};

type Props = {
  isSubmitting: boolean;
  onSubmit: (payload: LeadSearchPayload) => Promise<void>;
  initialValues?: Partial<LeadSearchPayload> | null;
  initialTaskId?: string | null;
};

type FormErrors = Partial<Record<'product_name' | 'countries' | 'languages' | 'target_count', string>>;

const ENGLISH_CODE = 'en';
const CONTINENT_LABELS: Record<string, string> = {
  Africa: '非洲',
  Asia: '亚洲',
  Europe: '欧洲',
  'North America': '北美洲',
  'South America': '南美洲',
  Oceania: '大洋洲',
};

export function LeadSearchForm({ isSubmitting, onSubmit, initialValues, initialTaskId }: Props) {
  const defaultMode: 'live' | 'demo' = import.meta.env.DEV ? 'demo' : 'live';
  const [productName, setProductName] = useState('industrial valve');
  const [selectedContinents, setSelectedContinents] = useState<string[]>(['Asia']);
  const [selectedCountries, setSelectedCountries] = useState<string[]>(['CN', 'IN']);
  const [selectedLanguages, setSelectedLanguages] = useState<string[]>([ENGLISH_CODE, 'zh']);
  const [searchMode, setSearchMode] = useState<'live' | 'demo'>(defaultMode);
  const [countrySearch, setCountrySearch] = useState('');
  const [targetCountInput, setTargetCountInput] = useState('');
  const [errors, setErrors] = useState<FormErrors>({});
  const appliedTaskIdRef = useRef<string | null>(null);

  const groupedCountries = useMemo(() => selectedContinents.map((continent) => {
    const items = geoData
      .filter((entry) => entry.continent === continent)
      .sort((a, b) => a.name_en.localeCompare(b.name_en))
      .filter((entry) => {
        const keyword = countrySearch.trim().toLowerCase();
        if (!keyword) return true;
        return `${entry.name_en} ${entry.name_zh} ${entry.name_local} ${entry.code}`.toLowerCase().includes(keyword);
      });
    return { continent, items };
  }).filter((group) => group.items.length > 0), [countrySearch, selectedContinents]);

  const visibleCountries = useMemo(() => groupedCountries.flatMap((group) => group.items), [groupedCountries]);
  const selectedCountryEntries = useMemo(() => geoData
    .filter((entry) => selectedCountries.includes(entry.code))
    .sort((a, b) => a.name_en.localeCompare(b.name_en)), [selectedCountries]);

  const availableLanguages = useMemo(() => {
    const fromCountries = geoData.filter((entry) => selectedCountries.includes(entry.code)).flatMap((entry) => entry.languages);
    const deduped = Array.from(new Set([ENGLISH_CODE, ...fromCountries]));
    return deduped.sort((a, b) => (LANGUAGE_LABELS[a] ?? a).localeCompare(LANGUAGE_LABELS[b] ?? b));
  }, [selectedCountries]);

  useEffect(() => {
    const allowedCodes = new Set(selectedContinents.flatMap((continent) => geoData.filter((entry) => entry.continent === continent).map((entry) => entry.code)));
    setSelectedCountries((current) => current.filter((code) => allowedCodes.has(code)));
  }, [selectedContinents]);

  useEffect(() => {
    setSelectedLanguages((current) => {
      const next = current.filter((language) => availableLanguages.includes(language));
      return next.length > 0 ? next : [ENGLISH_CODE].filter((language) => availableLanguages.includes(language));
    });
  }, [availableLanguages]);

  useEffect(() => {
    if (!initialValues) return;
    if (initialTaskId && appliedTaskIdRef.current === initialTaskId) return;
    setProductName(initialValues.product_name ?? '');
    setSelectedContinents(initialValues.continents ?? []);
    setSelectedCountries((initialValues.countries ?? []).map((value) => geoData.find((entry) => entry.name_en === value || entry.code === value)?.code ?? value));
    setSelectedLanguages(initialValues.languages ?? [ENGLISH_CODE]);
    setSearchMode((initialValues.mode as 'live' | 'demo') ?? defaultMode);
    setTargetCountInput(initialValues.target_count ? String(initialValues.target_count) : '');
    setErrors({});
    appliedTaskIdRef.current = initialTaskId ?? null;
  }, [defaultMode, initialTaskId, initialValues]);

  const toggleContinent = (continent: string) => {
    setSelectedContinents((current) => {
      if (!current.includes(continent)) return [...current, continent];
      const next = current.filter((item) => item !== continent);
      const codes = new Set(geoData.filter((entry) => entry.continent === continent).map((entry) => entry.code));
      setSelectedCountries((existing) => existing.filter((code) => !codes.has(code)));
      return next;
    });
  };

  const toggleCountry = (code: string) => setSelectedCountries((current) => current.includes(code) ? current.filter((item) => item !== code) : [...current, code]);
  const toggleLanguage = (language: string) => setSelectedLanguages((current) => current.includes(language) ? current.filter((item) => item !== language) : [...current, language]);

  const bulkToggleContinent = (continent: string, mode: 'select' | 'clear') => {
    const codes = geoData.filter((entry) => entry.continent === continent).map((entry) => entry.code);
    setSelectedCountries((current) => {
      const next = new Set(current);
      codes.forEach((code) => mode === 'select' ? next.add(code) : next.delete(code));
      return Array.from(next);
    });
  };

  const validate = (): LeadSearchPayload | null => {
    const nextErrors: FormErrors = {};
    const trimmedName = productName.trim();
    if (!trimmedName) nextErrors.product_name = '请输入产品名称';
    if (selectedCountries.length === 0) nextErrors.countries = '请至少选择一个国家/地区';
    if (selectedLanguages.length === 0) nextErrors.languages = '请至少选择一种搜索语言';

    let targetCount: number | null = null;
    if (targetCountInput.trim()) {
      const parsed = Number(targetCountInput);
      if (!Number.isInteger(parsed) || parsed < 1) nextErrors.target_count = '目标客户数量必须是大于等于 1 的正整数';
      else targetCount = parsed;
    }

    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return null;
    return {
      product_name: trimmedName,
      continents: selectedContinents,
      countries: selectedCountries.map((code) => geoData.find((entry) => entry.code === code)?.name_en ?? code),
      languages: selectedLanguages,
      target_count: targetCount,
      mode: searchMode,
    };
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const payload = validate();
    if (payload) await onSubmit(payload);
  };

  return (
    <form className="search-form-stack" onSubmit={submit}>
      <section className="search-block panel">
        <div className="block-heading"><h3>区块 A：产品信息</h3><div className="block-divider" /></div>
        <label className="field">
          <span>产品名称</span>
          <input className={`input ${errors.product_name ? 'input-error' : ''}`} value={productName} onChange={(e) => setProductName(e.target.value)} placeholder="例如：industrial valve" />
          {errors.product_name ? <small className="field-error">{errors.product_name}</small> : null}
        </label>
      </section>

      <section className="search-block panel">
        <div className="block-heading"><h3>区块 B：目标市场</h3><div className="block-divider" /></div>

        <div className="field">
          <span>大洲（复选框组）</span>
          <div className="continent-row">
            {CONTINENTS.map((continent) => (
              <label key={continent} className="chip-checkbox">
                <input type="checkbox" checked={selectedContinents.includes(continent)} onChange={() => toggleContinent(continent)} />
                <span>{CONTINENT_LABELS[continent] ?? continent}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="field">
          <div className="field-inline">
            <div className="group-title-wrap">
              <span>国家 / 地区（按已选大洲过滤）</span>
              <small className="selection-counter">已选 {selectedCountries.length} 个</small>
            </div>
            {visibleCountries.length > 20 ? <input className="input country-search" value={countrySearch} onChange={(e) => setCountrySearch(e.target.value)} placeholder="🔍 搜索国家（中/英）..." /> : null}
          </div>
          <div className={`country-panel ${errors.countries ? 'input-error' : ''}`}>
            {groupedCountries.length === 0 ? <div className="muted-text">请先选择至少一个大洲。</div> : null}
            {groupedCountries.map((group) => {
              const total = group.items.length;
              const selectedCount = group.items.filter((item) => selectedCountries.includes(item.code)).length;
              return (
                <section key={group.continent} className="country-group">
                  <div className="field-inline country-group-header">
                    <div className="group-title-wrap">
                      <strong>{CONTINENT_LABELS[group.continent] ?? group.continent}</strong>
                      <small className="selection-counter">已选 {selectedCount} / 总 {total}</small>
                    </div>
                    <div className="mini-actions">
                      <button type="button" className={`mini-btn mini-btn-select ${selectedCount === total && total > 0 ? 'is-active' : ''}`} onClick={() => bulkToggleContinent(group.continent, 'select')}>全选</button>
                      <button type="button" className="mini-btn mini-btn-clear" disabled={selectedCount === 0} onClick={() => bulkToggleContinent(group.continent, 'clear')}>取消全选</button>
                    </div>
                  </div>
                  <div className="country-grid">
                    {group.items.map((entry) => (
                      <label key={entry.code} className="checkbox-card compact">
                        <input type="checkbox" checked={selectedCountries.includes(entry.code)} onChange={() => toggleCountry(entry.code)} />
                        <span className={!entry.name_zh ? "missing-zh" : undefined}>{entry.name_zh ? `${entry.name_zh}（${entry.name_en}）` : `[缺失中文名]（${entry.name_en}）`}</span>
                      </label>
                    ))}
                  </div>
                </section>
              );
            })}
          </div>
          {selectedCountryEntries.length > 0 ? (
            <div className="selection-summary-card">
              <div className="field-inline">
                <strong>当前目标市场</strong>
                <small className="selection-counter">{selectedCountryEntries.length} 个国家 / 地区</small>
              </div>
              <div className="selection-summary-list">
                {selectedCountryEntries.map((entry) => (
                  <span key={entry.code} className="selection-pill">
                    {entry.name_zh || entry.name_en}
                    <small>{CONTINENT_LABELS[entry.continent] ?? entry.continent}</small>
                  </span>
                ))}
              </div>
            </div>
          ) : null}
          {errors.countries ? <small className="field-error">{errors.countries}</small> : null}
        </div>

        <div className="field">
          <div className="field-inline">
            <div className="group-title-wrap"><span>搜索语言（复选框组）</span><small className="selection-counter">已选 {selectedLanguages.length} 种</small></div>
            <div className="mini-actions">
              <button className={`mini-btn mini-btn-select ${selectedLanguages.length === availableLanguages.length && availableLanguages.length > 0 ? 'is-active' : ''}`} type="button" onClick={() => setSelectedLanguages(availableLanguages)}>全选</button>
              <button className="mini-btn mini-btn-clear" type="button" disabled={selectedLanguages.length === 0} onClick={() => setSelectedLanguages([])}>取消全选</button>
            </div>
          </div>
          <div className={`checkbox-grid ${errors.languages ? 'checkbox-grid-error' : ''}`}>
            {availableLanguages.map((language) => (
              <label key={language} className="checkbox-card compact">
                <input type="checkbox" checked={selectedLanguages.includes(language)} onChange={() => toggleLanguage(language)} />
                <span>{LANGUAGE_LABELS[language] ?? language}</span>
              </label>
            ))}
          </div>
          {errors.languages ? <small className="field-error">{errors.languages}</small> : null}
        </div>
      </section>

      <section className="search-block panel">
        <div className="block-heading"><h3>区块 C：搜索配置</h3><div className="block-divider" /></div>
        <div className="config-row">
          <label className="field config-field">
            <span>目标客户数量（可选）</span>
            <input className={`input ${errors.target_count ? 'input-error' : ''}`} type="number" min={1} step={1} inputMode="numeric" value={targetCountInput} onChange={(e) => setTargetCountInput(e.target.value)} placeholder="留空 = 搜索全部" />
            {errors.target_count ? <small className="field-error">{errors.target_count}</small> : <small className="field-help">默认先按目标数量的 2 倍抓取候选，不够时再按 1 倍逐步扩容；无法证明属于目标市场的企业会被严格过滤。</small>}
          </label>
          <div className="field config-field">
            <span>搜索模式</span>
            <div className="continent-row">
              <label className="chip-checkbox">
                <input type="radio" name="search-mode" checked={searchMode === 'live'} onChange={() => setSearchMode('live')} />
                <span>实时搜索</span>
              </label>
              <label className="chip-checkbox">
                <input type="radio" name="search-mode" checked={searchMode === 'demo'} onChange={() => setSearchMode('demo')} />
                <span>演示模式</span>
              </label>
            </div>
            <small className="field-help">演示模式会生成可交互的样例结果，适合本地联调；实时搜索会走外部检索服务。</small>
          </div>
          <div className="actions config-actions"><button className="button" type="submit" disabled={isSubmitting}>{isSubmitting ? '搜索中…' : '开始搜索'}</button></div>
        </div>
      </section>
    </form>
  );
}
