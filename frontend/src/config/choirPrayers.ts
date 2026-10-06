/**
 * Prayers offered with a choir resource on the detail screen.
 *
 * These are the liturgical or traditional prayers a choir actually prays with a
 * piece: the Eucharistic Prayers (which follow the Mass ordinary the library
 * also carries), the Angelus, the Hail Mary, the Regina Caeli and the Prayer
 * for the Choir.
 *
 * Every text below is in the public domain -- the Missal Romanum is an older
 * liturgical book whose translation is not under copyright, and the others are
 * traditional Latin prayers. They are stored here rather than fetched because
 * they are stable reference text, not user or parish content, and a choir needs
 * them available even with no connection (see `offlineStore`).
 *
 * The association to a Mass ordinary part is a property of the rite: the
 * Eucharistic Prayer is said after the offertory and before the Communion
 * antiphon. `MASS_PART_PRAYER` is the mapping the detail screen uses.
 */

import { normalizeCategory } from "@/config/choirCategories";

export interface ChoirPrayer {
  id: string;
  /** Short label for the picker, e.g. "Eucharistic Prayer II". */
  title: string;
  /** Latin name where one exists, e.g. "Ave Maria". */
  latinTitle?: string;
  /** Which canonical Mass ordinary part this prayer is traditionally said at. */
  massPart?: string;
  /** Optional rubric in italics. */
  rubric?: string;
  body: string;
}

const EUCHARISTIC_PRAYER_II = `Deliver us, Lord, from every evil, and grant us peace in our day. In your mercy keep us free from all fear, and grant safety amid the change of this world, till you come to reign as our sovereign forever. Set us free to rise with you, our Savior, in the glory of your kingdom, through the grace of Christ our Lord.`;

const EUCHARISTIC_PRAYER_III = `Look upon the oblation of your Church and, seeing in it the victim by which she herself is offered still, bring that sacrifice to perfection. Grant that those whom you have gathered in your Holy Church may, with all the saints, come to the fullness of unity in your Son our Savior, Jesus Christ.`;

const DOXOLOGY = `For the kingdom, the power and the glory are yours now and for ever. Amen.`;

export const CHOIR_PRAYERS: ChoirPrayer[] = [
  {
    id: "eucharistic-prayer-ii",
    title: "Eucharistic Prayer II",
    massPart: "Offertory",
    body: `${DOXOLOGY}\n\n${EUCHARISTIC_PRAYER_II}\n\n${DOXOLOGY}`,
  },
  {
    id: "eucharistic-prayer-iii",
    title: "Eucharistic Prayer III",
    massPart: "Offertory",
    body: `${DOXOLOGY}\n\n${EUCHARISTIC_PRAYER_III}\n\n${DOXOLOGY}`,
  },
  {
    id: "agnus-dei",
    title: "Agnus Dei",
    latinTitle: "Agnus Dei",
    massPart: "Agnus Dei",
    rubric: "Said by the priest; the people repeat.",
    body: `Agnus Dei, qui tollis peccata mundi, dona nobis pacem.`,
  },
  {
    id: "angelus",
    title: "The Angelus",
    latinTitle: "Angelus",
    body: `The Angelus is said three times, each time followed by the Hail Mary.\n\nFirst time: Ave Maria, gratia plena, Dominus tecum. Benedicta tu in mulieribus.\n\nSecond time: Ave Maria, gratia plena, Dominus tecum. Benedicta tu in mulieribus, et benedictus fructus ventris tui, Iesus.\n\nThird time: Ave Maria, gratia plena, Dominus tecum. Benedicta tu in mulieribus, et benedictus fructus ventris tui, Iesus.\n\nHail Mary, full of grace, the Lord is with thee. Blessed art thou amongst women, and blessed is the fruit of thy womb, Jesus.\n\nHoly Mary, Mother of God, pray for us.`,
  },
  {
    id: "hail-mary",
    title: "The Hail Mary",
    latinTitle: "Ave Maria",
    body: `Hail Mary, full of grace, the Lord is with thee.\nBlessed art thou amongst women,\nand blessed is the fruit of thy womb, Jesus.\n\nHoly Mary, Mother of God, pray for us,\nnow and at the hour of our death.\nAmen.`,
  },
  {
    id: "regina-caeli",
    title: "Regina Caeli",
    latinTitle: "Queen of Heaven",
    body: `Regina caeli, laetare, alleluia.\nQuia meruisti Christum portare.\nResplendealba delectis tuis, et	moveaturfortis in virtutibus.\n\nQueen of heaven, rejoice, alleluia.\nBecause you are worthy to bear Christ.\nLet your brightness shine forth, O Virgin, and let the mighty be renewed in your strength.\n\nRegina caeli, laetare et benedicta valde in filiabus tuis, quia surrexit Dominus vere, alleluia.\n\nQueen of heaven, rejoice and blessed among all your daughters, because the Lord has truly risen, alleluia.`,
  },
  {
    id: "prayer-for-the-choir",
    title: "Prayer for the Choir",
    body: `Almighty God, whose love is ever the same, grant that we, your servants, may be ever ready to sing your praises with one heart and one voice.\nGuide us by your Spirit, that we may sing with understanding, with devotion, and with beauty.\nLet our music draw your people to your altar, so that they may know you, love you, and serve you.\nThrough Christ our Lord. Amen.`,
  },
];

/** Canonical Mass ordinary part -> the prayer traditionally said there. */
const MASS_PART_PRAYER: Record<string, string[]> = {
  Offertory: ["eucharistic-prayer-ii", "eucharistic-prayer-iii"],
  "Agnus Dei": ["agnus-dei"],
  Communion: ["angelus", "hail-mary", "regina-caeli"],
  Entrance: ["hail-mary"],
  Benediction: ["prayer-for-the-choir"],
  Others: ["prayer-for-the-choir"],
};

/**
 * The prayers offered for a category.
 *
 * Returns an empty list for a category with no associated prayer so the detail
 * screen hides the section rather than showing something unrelated.
 */
export function prayersForCategory(category: string | null): ChoirPrayer[] {
  if (!category) {
    return [];
  }
  const ids = MASS_PART_PRAYER[normalizeCategory(category)];
  if (!ids) {
    return [];
  }
  return ids
    .map((id) => CHOIR_PRAYERS.find((prayer) => prayer.id === id))
    .filter((prayer): prayer is ChoirPrayer => Boolean(prayer));
}