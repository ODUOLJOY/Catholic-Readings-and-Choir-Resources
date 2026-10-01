import React, { useState, useEffect } from 'react';
import { View, Text, Pressable, StyleSheet, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { api } from '../lib/api';

interface DirectoryOption {
  id: number;
  name: string;
}

export default function ProfileSetup() {
  const router = useRouter();
  const [step, setStep] = useState<'diocese' | 'deanery' | 'parish'>('diocese');
  const [dioceses, setDioceses] = useState<DirectoryOption[]>([]);
  const [deaneries, setDeaneries] = useState<DirectoryOption[]>([]);
  const [parishes, setParishes] = useState<DirectoryOption[]>([]);
  const [selectedDiocese, setSelectedDiocese] = useState<DirectoryOption | null>(null);
  const [selectedDeanery, setSelectedDeanery] = useState<DirectoryOption | null>(null);
  const [selectedParish, setSelectedParish] = useState<DirectoryOption | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchDioceses = async () => {
    try {
      const response = await api.get('/api/v1/locations/dioceses');
      setDioceses(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void Promise.resolve().then(fetchDioceses);
  }, []);

  const selectDiocese = async (diocese: DirectoryOption) => {
    setSelectedDiocese(diocese);
    setLoading(true);
    try {
      const response = await api.get(`/api/v1/locations/dioceses/${diocese.id}/deaneries`);
      setDeaneries(response.data);
      setStep('deanery');
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const selectDeanery = async (deanery: DirectoryOption) => {
    setSelectedDeanery(deanery);
    setLoading(true);
    try {
      const response = await api.get(`/api/v1/locations/deaneries/${deanery.id}/parishes`);
      setParishes(response.data);
      setStep('parish');
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const submit = async () => {
    if (!selectedDiocese || !selectedDeanery || !selectedParish) return;

    try {
      await api.put('/api/v1/users/me/location', {
        parish_id: selectedParish.id,
        deanery_id: selectedDeanery.id,
        diocese_id: selectedDiocese.id,
      });
      router.replace('/(tabs)');
    } catch (error) {
      console.error(error);
    }
  };

  if (loading) return <ActivityIndicator style={styles.container} />;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Set up your parish</Text>
      {step === 'diocese' && (
        <View>
          <Text>Select Diocese</Text>
          {dioceses.map(d => (
            <Pressable key={d.id} onPress={() => selectDiocese(d)} style={styles.button}>
              <Text>{d.name}</Text>
            </Pressable>
          ))}
        </View>
      )}
      {step === 'deanery' && (
        <View>
          <Text>Select Deanery</Text>
          {deaneries.map(d => (
            <Pressable key={d.id} onPress={() => selectDeanery(d)} style={styles.button}>
              <Text>{d.name}</Text>
            </Pressable>
          ))}
        </View>
      )}
      {step === 'parish' && (
        <View>
          <Text>Select Parish</Text>
          {parishes.map(p => (
            <Pressable key={p.id} onPress={() => setSelectedParish(p)} style={[styles.button, selectedParish?.id === p.id && styles.selected]}>
              <Text>{p.name}</Text>
            </Pressable>
          ))}
          <Pressable onPress={submit} style={styles.submitButton} disabled={!selectedParish}>
            <Text style={styles.submitText}>Complete Setup</Text>
          </Pressable>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20, justifyContent: 'center' },
  title: { fontSize: 24, marginBottom: 20 },
  button: { padding: 15, backgroundColor: '#f0f0f0', marginBottom: 10, borderRadius: 5 },
  selected: { backgroundColor: '#d0d0d0' },
  submitButton: { padding: 15, backgroundColor: '#007AFF', borderRadius: 5, marginTop: 20 },
  submitText: { color: 'white', textAlign: 'center' }
});
