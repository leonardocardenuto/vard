import { Text } from 'react-native';

import { styles } from '../auth_screen';

export function TermsText() {
  return (
    <Text style={styles.termsText}>
      Ao continuar, você concorda com os <Text style={styles.linkText}>Termos de{'\n'}Serviço</Text> e a <Text style={styles.linkText}>Política de Privacidade.</Text>
    </Text>
  );
}
