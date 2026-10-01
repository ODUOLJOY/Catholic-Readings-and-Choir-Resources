import React, { useState } from 'react';
import { View, Text, TextInput, Button, StyleSheet, Alert } from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { api } from '@/lib/api';

export default function ReportContent() {
  const { resourceType, resourceId } = useLocalSearchParams<{ resourceType: string; resourceId: string }>();
  const [reason, setReason] = useState('');
  const [description, setDescription] = useState('');

  const handleSubmit = async () => {
    if (!reason) {
      Alert.alert('Error', 'Please provide a reason for the report.');
      return;
    }
    try {
      await api.post('/api/reports/', {
        resource_type: resourceType,
        resource_id: parseInt(resourceId),
        reason,
        description,
      });
      Alert.alert('Success', 'Report submitted successfully.');
      router.back();
    } catch (error) {
      Alert.alert('Error', 'Failed to submit report.');
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Report Content</Text>
      <TextInput
        style={styles.input}
        placeholder="Reason (e.g., Inappropriate content)"
        value={reason}
        onChangeText={setReason}
      />
      <TextInput
        style={[styles.input, { height: 100 }]}
        placeholder="Details"
        value={description}
        onChangeText={setDescription}
        multiline
      />
      <Button title="Submit Report" onPress={handleSubmit} color="#0B6623" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20, backgroundColor: '#fff' },
  title: { fontSize: 24, fontWeight: 'bold', marginBottom: 20, color: '#0B6623' },
  input: { borderWidth: 1, borderColor: '#ccc', padding: 10, marginBottom: 15, borderRadius: 5 },
});
