import AsyncStorage from "@react-native-async-storage/async-storage";
import { File, Paths } from "expo-file-system";
import { API_URL } from "@/config/api";
import { api } from "@/lib/api";

const KEY = "OFFLINE_RESOURCE_FILES";
type CachedResource = { id: number; uri: string; fileUrl: string; title: string };
type CacheInput = {
  id: number;
  title: string;
  file_url: string;
  file_type?: string;
};

async function readCache(): Promise<CachedResource[]> {
  const value = await AsyncStorage.getItem(KEY);
  return value ? JSON.parse(value) : [];
}

export async function cacheResource(resource: CacheInput) {
  await api.get(`/api/choir/${resource.id}`);
  const url = new URL(resource.file_url, API_URL).toString();
  const extension =
    resource.file_type
      ? resource.file_type.split("/").pop()?.toLowerCase() || "bin"
      : resource.file_url.split(".").pop()?.split("?")[0] || "bin";
  const safeTitle = resource.title.replace(/[^a-z0-9]+/gi, "-").toLowerCase();
  const directory = Paths.document.createDirectory("choir");
  const destination = new File(directory, `${resource.id}-${safeTitle}.${extension}`);
  const token = await AsyncStorage.getItem("access_token");
  const file = await File.downloadFileAsync(url, destination, {
    idempotent: true,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  const cached = (await readCache()).filter((item) => item.id !== resource.id);
  cached.push({ id: resource.id, uri: file.uri, fileUrl: resource.file_url, title: resource.title });
  await AsyncStorage.setItem(KEY, JSON.stringify(cached));
  return file.uri;
}

export async function getCachedResource(resourceId: number) {
  const item = (await readCache()).find((entry) => entry.id === resourceId);
  if (!item) return null;
  return new File(item.uri).exists ? item.uri : null;
}

/**
 * Every resource this device currently holds a local copy of.
 *
 * Used by the library screen to offer an offline shelf. Entries whose file has
 * since been removed outside the app are dropped here rather than shown as
 * available and then failing to open.
 */
export async function listCachedResources() {
  const entries = await readCache();
  const alive: CachedResource[] = [];
  for (const entry of entries) {
    const file = new File(entry.uri);
    if (await file.exists) alive.push(entry);
  }
  if (alive.length !== entries.length) {
    await AsyncStorage.setItem(KEY, JSON.stringify(alive));
  }
  return alive;
}

export async function removeCachedResource(resourceId: number) {
  const cached = await readCache();
  const item = cached.find((entry) => entry.id === resourceId);
  if (item) new File(item.uri).delete();
  await AsyncStorage.setItem(KEY, JSON.stringify(cached.filter((entry) => entry.id !== resourceId)));
}

export async function clearCache() {
  for (const item of await readCache()) new File(item.uri).delete();
  await AsyncStorage.removeItem(KEY);
}