import React from 'react';
import { TouchableOpacity, Text, StyleSheet } from 'react-native';
import { router } from 'expo-router';

interface ReportButtonProps {
  resourceType: string;
  resourceId: number;
}

export const ReportButton: React.FC<ReportButtonProps> = ({ resourceType, resourceId }) => {
  return (
    <TouchableOpacity
      style={styles.button}
      onPress={() => router.push({ pathname: '/report-content', params: { resourceType, resourceId: resourceId.toString() } })}
    >
      <Text style={styles.text}>Report Content</Text>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  button: {
    marginTop: 20,
    padding: 10,
    backgroundColor: '#f8d7da',
    borderRadius: 5,
    alignItems: 'center',
  },
  text: {
    color: '#721c24',
    fontWeight: 'bold',
  },
});
