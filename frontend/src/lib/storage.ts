import AsyncStorage from "@react-native-async-storage/async-storage";

export enum StorageKeys {
  PENDING_READINGS = "pending_readings",
  PENDING_UPLOADS = "pending_uploads",
  USER_PREFERENCES = "user_preferences",
  OFFLINE_DATA = "offline_data",
}

/**
 * Get a list from AsyncStorage
 */
export async function getList<T>(key: string): Promise<T[]> {
  try {
    const data = await AsyncStorage.getItem(key);
    if (!data) return [];
    return JSON.parse(data) as T[];
  } catch (error) {
    console.error(`Error retrieving ${key} from storage:`, error);
    return [];
  }
}

/**
 * Save a list to AsyncStorage
 */
export async function saveList<T>(
  key: string,
  data: T[]
): Promise<void> {
  try {
    await AsyncStorage.setItem(key, JSON.stringify(data));
  } catch (error) {
    console.error(`Error saving ${key} to storage:`, error);
    throw error;
  }
}

/**
 * Get a single item from AsyncStorage
 */
export async function getItem<T>(key: string): Promise<T | null> {
  try {
    const data = await AsyncStorage.getItem(key);
    if (!data) return null;
    return JSON.parse(data) as T;
  } catch (error) {
    console.error(`Error retrieving ${key} from storage:`, error);
    return null;
  }
}

/**
 * Save a single item to AsyncStorage
 */
export async function saveItem<T>(key: string, data: T): Promise<void> {
  try {
    await AsyncStorage.setItem(key, JSON.stringify(data));
  } catch (error) {
    console.error(`Error saving ${key} to storage:`, error);
    throw error;
  }
}

/**
 * Remove an item from AsyncStorage
 */
export async function removeItem(key: string): Promise<void> {
  try {
    await AsyncStorage.removeItem(key);
  } catch (error) {
    console.error(`Error removing ${key} from storage:`, error);
    throw error;
  }
}

/**
 * Clear all items from AsyncStorage
 */
export async function clearAll(): Promise<void> {
  try {
    await AsyncStorage.clear();
  } catch (error) {
    console.error("Error clearing storage:", error);
    throw error;
  }
}
