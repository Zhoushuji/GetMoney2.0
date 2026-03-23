import { FormEvent, useEffect, useMemo, useState } from 'react';

import { CONTINENTS, LANGUAGE_LABELS, geoData } from '../../data/geo';

export type LeadSearchPayload = {
  product_name: string;
  continents: string[];
  countries: string[];
  languages: string[];
  target_count: number | null;
};

type Props = {
  isSubmitting: boolean;
  onSubmit: (payload: LeadSearchPayload) => Promise<void>;
};

type FormErrors = Partial<Record<'product_name' | 'countries' | 'languages' | 'target_count', string>>;

const ENGLISH_CODE = 'en';

export function LeadSearchForm({ isSubmitting, onSubmit }: Props) {
  const [productName, setProductName] = useState('industrial valve');
  const [selectedContinents, setSelectedContinents] = useState<string[]>(['Europe']);
  const [selectedCountries, setSelectedCountries] = useState<string[]>(['DE']);
  const [selectedLanguages, setSelectedLanguages] = useState<string[]>([ENGLISH_CODE]);
  const [targetCountInput, setTargetCountInput] = useState('');
  const [errors, setErrors] = useState<FormErrors>({});

  const countries = useMemo(
    () => geoData.filter((entry) => selectedContinents.length === 0 || selectedContinents.includes(entry.continent)),
    [selectedContinents],
  );

  const availableLanguages = useMemo(() => {
    const fromCountries = geoData
      .filter((entry) => selectedCountries.includes(entry.code))
      .flatMap((entry) => entry.languages);
    const deduped = Array.from(new Set(fromCountries));
    const withoutEnglish = deduped.filter((language) => language !== ENGLISH_CODE).sort((a, b) => (LANGUAGE_LABELS[a] ?? a).localeCompare(LANGUAGE_LABELS[b] ?? b));
    return [ENGLISH_CODE, ...withoutEnglish];
  }, [selectedCountries]);

  useEffect(() => {
    setSelectedCountries((current: string[]) => current.filter((code: string) => countries.some((entry) => entry.code === code)));
  }, [countries]);

  useEffect(() => {
    setSelectedLanguages((current: string[]) => current.filter((language: string) => availableLanguages.includes(language)));
  }, [availableLanguages]);

  const validate = (): LeadSearchPayload | null => {
    const nextErrors: FormErrors = {};
    const trimmedName = productName.trim();

    if (!trimmedName) {
      nextErrors.product_name = '请输入产品名称';
    }
    if (selectedCountries.length === 0) {
      nextErrors.countries = '请至少选择一个国家';
    }
    if (selectedLanguages.length === 0) {
      nextErrors.languages = '请至少选择一种搜索语言';
    }

    let targetCount: number | null = null;
    if (targetCountInput.trim()) {
      const parsed = Number(targetCountInput);
      if (!Number.isInteger(parsed) || parsed < 1) {
        nextErrors.target_count = '目标客户数量必须是大于等于 1 的正整数';
      } else {
        targetCount = parsed;
      }
    }

    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      return null;
    }

    return {
      product_name: trimmedName,
      continents: selectedContinents,
      countries: selectedCountries.map((code) => geoData.find((entry) => entry.code === code)?.name_en ?? code),
      languages: selectedLanguages,
      target_count: targetCount,
    };
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const payload = validate();
    if (!payload) {
      return;
    }
    await onSubmit(payload);
  };

  const toggleLanguage = (language: string) => {
    setSelectedLanguages((current: string[]) => current.includes(language)
      ? current.filter((item: string) => item !== language)
      : [...current, language],
    );
  };

  return (
    <form className="panel" onSubmit={submit}>
      <h2>Lead Discovery</h2>
      <div className="form-grid">
        <label className="field">
          <span>产品名称</span>
          <input
            className={`input ${errors.product_name ? 'input-error' : ''}`}
            value={productName}
            onChange={(e) => setProductName(e.target.value)}
            placeholder="例如：industrial valve"
          />
          {errors.product_name ? <small className="field-error">{errors.product_name}</small> : null}
        </label>
        <label className="field">
          <span>大洲</span>
          <select
            className="select"
            multiple
            value={selectedContinents}
            onChange={(e) => setSelectedContinents(Array.from(e.target.selectedOptions).map((o) => o.value))}
          >
            {CONTINENTS.map((continent) => (
              <option key={continent} value={continent}>{continent}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>国家</span>
          <select
            className={`select ${errors.countries ? 'input-error' : ''}`}
            multiple
            value={selectedCountries}
            onChange={(e) => setSelectedCountries(Array.from(e.target.selectedOptions).map((o) => o.value))}
          >
            {countries.map((entry) => (
              <option key={entry.code} value={entry.code}>{entry.name_en} ({entry.code})</option>
            ))}
          </select>
          {errors.countries ? <small className="field-error">{errors.countries}</small> : <small className="field-help">按住 Ctrl / Command 可多选。</small>}
        </label>
        <label className="field">
          <span>目标客户数量（可选）</span>
          <input
            className={`input ${errors.target_count ? 'input-error' : ''}`}
            type="number"
            min={1}
            step={1}
            inputMode="numeric"
            value={targetCountInput}
            onChange={(e) => setTargetCountInput(e.target.value)}
            placeholder="留空 = 搜索全部"
          />
          {errors.target_count ? <small className="field-error">{errors.target_count}</small> : <small className="field-help">设置后系统将在获得足够有效结果时自动停止搜索。</small>}
        </label>
      </div>

      <div className="field" style={{ marginTop: 16 }}>
        <div className="field-inline">
          <span>语言</span>
          <div className="inline-actions">
            <button className="text-button" type="button" onClick={() => setSelectedLanguages(availableLanguages)}>全选</button>
            <button className="text-button" type="button" onClick={() => setSelectedLanguages([])}>取消全选</button>
          </div>
        </div>
        <div className={`checkbox-grid ${errors.languages ? 'checkbox-grid-error' : ''}`}>
          {availableLanguages.map((language) => (
            <label key={language} className="checkbox-card">
              <input
                type="checkbox"
                checked={selectedLanguages.includes(language)}
                onChange={() => toggleLanguage(language)}
              />
              <span>{LANGUAGE_LABELS[language] ?? language} ({language})</span>
            </label>
          ))}
        </div>
        {errors.languages ? <small className="field-error">{errors.languages}</small> : null}
      </div>

      <div className="actions" style={{ marginTop: 20 }}>
        <button className="button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? '搜索中…' : '启动异步搜索'}
        </button>
      </div>
    </form>
  );
}
