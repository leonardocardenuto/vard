import { Text } from 'react-native';

import { styles } from '../auth_screen';

export function TermsText() {
  return (
    <Text style={styles.termsText}>
      Ao continuar, voce concorda com os <Text style={styles.linkText}>Termos de{'\n'}Servico</Text> e a <Text style={styles.linkText}>Politica de Privacidade.</Text>
    </Text>
  );
}
