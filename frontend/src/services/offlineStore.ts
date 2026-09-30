import AsyncStorage from "@react-native-async-storage/async-storage";
import { File, Paths } from "expo-file-system";
import { API_URL } from "@/config/api";

const KEY = "OFFLINE_RESOURCE_FILES";
type CachedResource = { id: number; uri: string; fileUrl: string; title: string };

async function readCache(): Promise<CachedResource[]> {
  const value = await AsyncStorage.getItem(KEY);
  return value ? JSON.parse(value) : [];
}

export async function cacheResource(resource: { id: number; title: string; file_url: string }) {
  const url = new URL(resource.file_url, API_URL).toString();
  const extension = resource.file_url.split(".").pop()?.split("?")[0] || "bin";
  const safeTitle = resource.title.replace(/[^a-z0-9]+/gi, "-").toLowerCase();
  const directory = Paths.document.createDirectory("choir");
  const destination = new File(directory, `${resource.id}-${safeTitle}.${extension}`);
  const file = await File.downloadFileAsync(url, destination, { idempotent: true });
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