import { api } from "@/lib/api";

export interface Favorite {
  id: number;
  user_id: number;
  resource_type: string;
  target_resource_id: number;
  created_at: string;
}

export const favoriteService = {
  getFavorites: async (): Promise<Favorite[]> => {
    const response = await api.get("/api/favorites");
    return response.data;
  },
  
  createFavorite: async (resource_type: string, target_resource_id: number): Promise<Favorite> => {
    const response = await api.post("/api/favorites", {
      resource_type,
      target_resource_id,
    });
    return response.data;
  },
  
  deleteFavorite: async (id: number): Promise<void> => {
    await api.delete(`/api/favorites/${id}`);
  },

  /**
   * Favourites for anonymous visitors, which never rejects.
   *
   * `GET /api/favorites` requires a session and answers `401` without one, while
   * the screens that display bookmarks are deliberately reachable signed-out --
   * `app/_layout.tsx` only redirects once auth state is known and treats public
   * screens as public.
   *
   * Pairing that call with a public data call inside a single `Promise.all` meant
   * one `401` discarded the successful response next to it, so a signed-out
   * visitor saw "No saints found." / "Saint not found." / "No reading selected."
   * on screens that were working perfectly. Screens must use this instead, so an
   * auth failure degrades the bookmark icon only.
   */
  getFavoritesOptional: async (): Promise<Favorite[]> => {
    try {
      return await favoriteService.getFavorites();
    } catch {
      return [];
    }
  },
};
