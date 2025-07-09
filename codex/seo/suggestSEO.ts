export interface SEOSuggestion {
  title: string;
  meta: string;
  headings: string[];
  faqs: string[];
}

export async function suggestSEO(url: string): Promise<SEOSuggestion> {
  return {
    title: `Optimized title for ${url}`,
    meta: `Meta description for ${url}`,
    headings: [`H1 for ${url}`, `H2 example`],
    faqs: [`FAQ about ${url}`],
  };
}
