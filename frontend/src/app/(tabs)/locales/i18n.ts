export const translations = {
  en: {
    home: "Home",
    readings: "Readings",
    choir: "Choir",
    saints: "Saints",
    settings: "Settings",
  },
  sw: {
    home: "Nyumbani",
    readings: "Masomo",
    choir: "Kwaya",
    saints: "Watakatifu",
    settings: "Mipangilio",
  },
};

export function getTranslation(
  language: "en" | "sw" = "en"
) {
  return translations[language];
}