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
};
