import { Feather } from '@expo/vector-icons';
import { Image, Pressable, ScrollView, Text, View } from 'react-native';
import { DatePickerModal } from 'react-native-paper-dates';

import { BackButton } from '../components/BackButton';
import { GradientButton } from '../components/GradientButton';
import { PaperAuthInput } from '../components/PaperAuthInput';
import { styles } from '../auth_screen';
import { SignupForm } from '../types/flow';

type SignupAuthScreenProps = {
  acceptedTerms: boolean;
  errorMessage: string;
  form: SignupForm;
  isPasswordVisible: boolean;
  isSubmitting: boolean;
  onBack: () => void;
  onChangeField: (field: keyof SignupForm, value: string) => void;
  onCreateAccount: () => void;
  onDismissBirthDatePicker: () => void;
  onOpenBirthDatePicker: () => void;
  onPickAvatar: () => void;
  onSelectBirthDate: (date: Date) => void;
  onTogglePassword: () => void;
  onToggleTerms: () => void;
  isBirthDatePickerOpen: boolean;
};

export function SignupAuthScreen({
  acceptedTerms,
  errorMessage,
  form,
  isPasswordVisible,
  isSubmitting,
  onBack,
  onChangeField,
  onCreateAccount,
  onDismissBirthDatePicker,
  onOpenBirthDatePicker,
  onPickAvatar,
  onSelectBirthDate,
  onTogglePassword,
  onToggleTerms,
  isBirthDatePickerOpen,
}: SignupAuthScreenProps) {
  return (
    <ScrollView contentContainerStyle={styles.signupContent} keyboardShouldPersistTaps="handled">
      <BackButton gradientLabel onPress={onBack} label="Concluir a criacao da conta" />

      <Pressable onPress={onPickAvatar} style={styles.avatarPicker}>
        {form.avatarUrl ? (
          <Image source={{ uri: form.avatarUrl }} style={styles.avatarImage} />
        ) : (
          <Feather color="#A7A7A7" name="camera" size={44} />
        )}
        <View style={styles.avatarPlus}>
          <Text style={styles.avatarPlusText}>+</Text>
        </View>
      </Pressable>

      <PaperAuthInput
        label="Primeiro Nome"
        onChangeText={(value) => onChangeField('firstName', value)}
        onClear={() => onChangeField('firstName', '')}
        value={form.firstName}
      />
      <PaperAuthInput
        label="Ultimo Nome"
        onChangeText={(value) => onChangeField('lastName', value)}
        onClear={() => onChangeField('lastName', '')}
        value={form.lastName}
      />
      <PaperAuthInput
        label="Data de Aniversario"
        editable={false}
        onChangeText={(value) => onChangeField('birthDate', value)}
        onClear={() => {
          onChangeField('birthDate', '');
          onChangeField('birthDateIso', '');
        }}
        onPress={onOpenBirthDatePicker}
        rightIcon="calendar"
        value={form.birthDate}
      />
      <PaperAuthInput
        label="Senha"
        onChangeText={(value) => onChangeField('password', value)}
        onToggleVisibility={onTogglePassword}
        passwordVisible={isPasswordVisible}
        secureTextEntry={!isPasswordVisible}
        value={form.password}
      />
      <PaperAuthInput
        label="Repita sua senha"
        onChangeText={(value) => onChangeField('confirmPassword', value)}
        onToggleVisibility={onTogglePassword}
        passwordVisible={isPasswordVisible}
        secureTextEntry={!isPasswordVisible}
        value={form.confirmPassword}
      />

      <Pressable onPress={onToggleTerms} style={styles.termsRow}>
        <View style={[styles.checkbox, acceptedTerms && styles.checkboxActive]}>
          {acceptedTerms ? <Feather color="#FFFFFF" name="check" size={12} /> : null}
        </View>
        <Text style={styles.termsRowText}>
          Ao criar a conta, eu concordo com os <Text style={styles.linkText}>Termos de{'\n'}Servico</Text> e a <Text style={styles.linkText}>Politica de Privacidade.</Text>
        </Text>
      </Pressable>

      {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}

      <View style={styles.signupButtonWrap}>
        <GradientButton disabled={isSubmitting} label={isSubmitting ? 'CRIANDO...' : 'CRIAR CONTA'} onPress={onCreateAccount} />
      </View>

      <DatePickerModal
        date={form.birthDateIso ? new Date(`${form.birthDateIso}T12:00:00`) : undefined}
        locale="pt"
        mode="single"
        onConfirm={({ date }) => {
          if (date) {
            onSelectBirthDate(date);
          }
        }}
        onDismiss={onDismissBirthDatePicker}
        saveLabel="Salvar"
        label="Selecione sua data de aniversario"
        visible={isBirthDatePickerOpen}
        validRange={{ endDate: new Date() }}
      />
    </ScrollView>
  );
}
