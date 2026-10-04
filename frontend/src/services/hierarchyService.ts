import { api } from "@/lib/api";

/**
 * Client for the ecclesiastical hierarchy endpoints.
 *
 * The hierarchy is a strict cascade:
 *
 *   country -> ecclesiastical province -> diocese -> deanery -> parish
 *
 * Every level is fetched from the API, so no directory data is hard-coded in
 * the app. The Military Ordinariate is a separate jurisdiction with no province
 * and is therefore excluded unless `includeOrdiniate` is requested.
 */

export interface HierarchyNode {
  id: number;
  name: string;
  code: string;
  is_active: boolean;
  verification_status: string;
  source_url: string | null;
}

export interface EcclesiasticalProvinceNode extends HierarchyNode {
  short_name: string | null;
  metropolitan_archdiocese_id: number | null;
}

export interface DioceseNode extends HierarchyNode {
  short_name: string | null;
  is_archdiocese: boolean;
  is_military_ordinariate: boolean;
  erected_on: string | null;
  deanery_count: number;
  website: string | null;
}

export interface DeaneryNode extends HierarchyNode {
  diocese_id: number;
  parish_count: number;
}

export interface ParishNode extends HierarchyNode {
  deanery_id: number;
  diocese_id: number;
  town: string | null;
  county: string | null;
  address: string | null;
}

/** The envelope every listing endpoint returns. */
export interface HierarchyPage<T> {
  count: number;
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  results: T[];
}

export interface ResolvedHierarchy {
  parish: HierarchyNode;
  deanery: HierarchyNode;
  diocese: HierarchyNode;
  province: HierarchyNode;
  country: HierarchyNode;
}

export interface HierarchySummary {
  countries: number;
  provinces: number;
  dioceses: number;
  deaneries: number;
  parishes: number;
}

async function fetchPage<T>(
  url: string,
  params: Record<string, string | number | boolean | undefined>,
): Promise<HierarchyPage<T>> {
  const response = await api.get<HierarchyPage<T>>(url, { params });
  return response.data;
}

export const hierarchyService = {
  listCountries(search?: string): Promise<HierarchyPage<HierarchyNode>> {
    return fetchPage<HierarchyNode>("/api/v1/hierarchy/countries", {
      search: search || undefined,
    });
  },

  listProvinces(
    countryId: number,
    search?: string,
  ): Promise<HierarchyPage<EcclesiasticalProvinceNode>> {
    return fetchPage<EcclesiasticalProvinceNode>("/api/v1/hierarchy/provinces", {
      country_id: countryId,
      search: search || undefined,
    });
  },

  listDioceses(
    provinceId: number,
    search?: string,
  ): Promise<HierarchyPage<DioceseNode>> {
    return fetchPage<DioceseNode>("/api/v1/hierarchy/dioceses", {
      province_id: provinceId,
      search: search || undefined,
    });
  },

  listAllDioceses(search?: string): Promise<HierarchyPage<DioceseNode>> {
    return fetchPage<DioceseNode>("/api/v1/hierarchy/dioceses", {
      search: search || undefined,
    });
  },

  listDeaneries(
    dioceseId: number,
    search?: string,
  ): Promise<HierarchyPage<DeaneryNode>> {
    return fetchPage<DeaneryNode>("/api/v1/hierarchy/deaneries", {
      diocese_id: dioceseId,
      search: search || undefined,
    });
  },

  listParishes(
    deaneryId: number,
    search?: string,
  ): Promise<HierarchyPage<ParishNode>> {
    return fetchPage<ParishNode>("/api/v1/hierarchy/parishes", {
      deanery_id: deaneryId,
      search: search || undefined,
    });
  },

  async resolveParish(parishId: number): Promise<ResolvedHierarchy> {
    const response = await api.get<ResolvedHierarchy>(
      "/api/v1/hierarchy/parishes/" + parishId,
    );
    return response.data;
  },

  async summary(): Promise<HierarchySummary> {
    const response = await api.get<HierarchySummary>("/api/v1/hierarchy/summary");
    return response.data;
  },
};