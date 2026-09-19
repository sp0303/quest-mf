import React, { useEffect } from "react";

export interface SEOProps {
  title: string;
  description?: string;
  keywords?: string;
  canonicalPath?: string;
}

const DEFAULT_TITLE =
  "quest-mf — Mutual Fund Quant Screener, Rolling Returns & SIP Analytics | a sharat patnayakuni's product";
const DEFAULT_DESCRIPTION =
  "India's premier quantitative mutual fund screener & portfolio analytics platform. Rolling returns, Sharpe ratio, alpha, backtesting & friction calculator. A Sharat Patnayakuni's product.";

export const SEO: React.FC<SEOProps> = ({
  title,
  description = DEFAULT_DESCRIPTION,
  keywords,
  canonicalPath,
}) => {
  useEffect(() => {
    // 1. Update Document Title
    const formattedTitle = title.includes("quest-mf") ? title : `${title} | quest-mf`;
    document.title = formattedTitle;

    // 2. Helper to set or create meta tags
    const setMetaTag = (attr: "name" | "property", key: string, content: string) => {
      let el = document.querySelector(`meta[${attr}="${key}"]`);
      if (!el) {
        el = document.createElement("meta");
        el.setAttribute(attr, key);
        document.head.appendChild(el);
      }
      el.setAttribute("content", content);
    };

    // 3. Update Description
    setMetaTag("name", "description", description);
    setMetaTag("property", "og:title", formattedTitle);
    setMetaTag("property", "og:description", description);
    setMetaTag("name", "twitter:title", formattedTitle);
    setMetaTag("name", "twitter:description", description);

    // 4. Update Keywords if present
    if (keywords) {
      setMetaTag("name", "keywords", keywords);
    }

    // 5. Update Canonical Link
    if (canonicalPath) {
      const fullUrl = `https://questmf.com${canonicalPath.startsWith("/") ? canonicalPath : `/${canonicalPath}`}`;
      let linkEl = document.querySelector('link[rel="canonical"]');
      if (!linkEl) {
        linkEl = document.createElement("link");
        linkEl.setAttribute("rel", "canonical");
        document.head.appendChild(linkEl);
      }
      linkEl.setAttribute("href", fullUrl);
      setMetaTag("property", "og:url", fullUrl);
    }

    return () => {
      // Revert to default on unmount if needed
      document.title = DEFAULT_TITLE;
    };
  }, [title, description, keywords, canonicalPath]);

  return null;
};
