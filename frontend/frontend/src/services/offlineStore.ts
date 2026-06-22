import AsyncStorage from "@react-native-async-storage/async-storage";

const KEY = "FULL_YEAR_CACHE";

export async function saveFullYear(data: any) {
  await AsyncStorage.setItem(KEY, JSON.stringify(data));
}

export async function getFullYear() {
  const data = await AsyncStorage.getItem(KEY);
  return data ? JSON.parse(data) : [];
}

export async function clearCache() {
  await AsyncStorage.removeItem(KEY);
}