type TaskParams = {
  keywords?: string[] | null;
  product_name?: string | null;
};

export function extractTaskKeywords(params?: TaskParams | null): string[] {
  const rawKeywords = params?.keywords ?? [];
  const normalized = rawKeywords
    .flatMap((keyword) => String(keyword ?? '').split(/[\n,，]+/))
    .map((keyword) => keyword.trim())
    .filter(Boolean);
  if (normalized.length > 0) {
    return Array.from(new Set(normalized));
  }

  const fallback = String(params?.product_name ?? '').trim();
  if (!fallback) return [];
  return Array.from(new Set(fallback.split(/[\n,，]+/).map((keyword) => keyword.trim()).filter(Boolean)));
}

export function formatTaskKeywordTitle(params?: TaskParams | null, fallback = '未命名任务'): string {
  const keywords = extractTaskKeywords(params);
  if (keywords.length === 0) return fallback;
  if (keywords.length === 1) return keywords[0];
  return `${keywords[0]} + ${keywords.length - 1} 个关键词`;
}
