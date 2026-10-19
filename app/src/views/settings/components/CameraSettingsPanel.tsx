import { VARD_COLORS } from '../../../theme/vardTheme';
import { Feather } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  Text,
  View,
} from 'react-native';
import { changeMyPassword, deleteMyAccount, updateMyProfile } from '../../../lib/api';
import { clearSession } from '../../../lib/session';

const SETTINGS_PANEL_FONTS = {
  regular: 'Poppins-Regular',
  semiBold: 'Poppins-SemiBold',
  bold: 'Poppins-Bold',
  extraBold: 'Poppins-ExtraBold',
} as const;

function formatPhone(value: string): string {
  const digits = value.replace(/\D/g, '').slice(0, 11);

  if (digits.length === 0) {
    return '';
  }

  if (digits.length <= 2) {
    return `(${digits}`;
  }

  if (digits.length <= 6) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
  }

  if (digits.length <= 10) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
  }

  return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
}

type CameraSettingsPanelProps = {
  accessToken: string;
  onLogout: () => void;
  userAvatarUrl: string | null;
  userEmail: string;
  userPhone: string | null;
  userName: string;
};

export function CameraSettingsPanel({
  accessToken,
  onLogout,
  userAvatarUrl,
  userEmail,
  userPhone,
  userName,
}: CameraSettingsPanelProps) {
  const fallbackAvatar = require('../../../../assets/default_avatar.png');

  const initialDisplayName = userName.trim() || 'usuário';
  const initialAvatarUrl = userAvatarUrl?.trim() ?? '';

  const [profileAvatarUri, setProfileAvatarUri] = useState(initialAvatarUrl);
  const [profileNameDraft, setProfileNameDraft] = useState(initialDisplayName);
  const [profilePassword, setProfilePassword] = useState('');
  const [profilePasswordConfirmation, setProfilePasswordConfirmation] = useState('');
  const [profileCurrentPassword, setProfileCurrentPassword] = useState('');
  const [profilePhoneDraft, setProfilePhoneDraft] = useState('');
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [profileStatus, setProfileStatus] = useState<{
    tone: 'success' | 'info' | 'error';
    message: string;
  } | null>(null);
  const [isPickingAvatar, setIsPickingAvatar] = useState(false);
  const [isDeletingAccount, setIsDeletingAccount] = useState(false);

  useEffect(() => {
    setProfileAvatarUri(initialAvatarUrl);
  }, [initialAvatarUrl]);

  useEffect(() => {
    setProfileNameDraft(initialDisplayName);
  }, [initialDisplayName]);

  useEffect(() => {
    setProfilePhoneDraft(formatPhone(userPhone ?? ''));
  }, [userPhone]);

  const profileAvatarSource = useMemo(
    () => (profileAvatarUri ? { uri: profileAvatarUri } : fallbackAvatar),
    [fallbackAvatar, profileAvatarUri]
  );

  const trimmedProfileName = profileNameDraft.trim();

  function pushProfileStatus(tone: 'success' | 'info' | 'error', message: string) {
    setProfileStatus({ tone, message });
  }

  function buildAvatarDataUri(asset: NonNullable<ImagePicker.ImagePickerSuccessResult['assets']>[number]) {
    if (!asset.base64) {
      throw new Error('A imagem selecionada precisa ser convertida em base64.');
    }

    const mimeType = asset.mimeType?.trim() || 'image/jpeg';
    return `data:${mimeType};base64,${asset.base64}`;
  }

  async function handlePickAvatar() {
    if (isSavingProfile || isChangingPassword || isDeletingAccount) {
      return;
    }

    setProfileStatus(null);
    setIsPickingAvatar(true);

    try {
      const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!permission.granted) {
        pushProfileStatus('error', 'Conceda acesso à galeria para trocar a foto.');
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        allowsEditing: true,
        aspect: [1, 1],
        base64: true,
        quality: 0.9,
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
      });

      if (!result.canceled && result.assets[0]) {
        const selectedAsset = result.assets[0];
        const previousAvatarUri = profileAvatarUri;
        const nextAvatarUri = buildAvatarDataUri(selectedAsset);

        setIsSavingProfile(true);
        setProfileAvatarUri(nextAvatarUri);

        try {
          const updatedUser = await updateMyProfile(accessToken, {
            avatar_url: nextAvatarUri,
          });
          setProfileAvatarUri(updatedUser.avatar_url ?? nextAvatarUri);
          pushProfileStatus('success', 'Foto de perfil salva na conta.');
        } catch {
          setProfileAvatarUri(previousAvatarUri);
          pushProfileStatus('error', 'Não foi possível salvar a foto de perfil.');
        } finally {
          setIsSavingProfile(false);
        }
      }
    } catch {
      pushProfileStatus('error', 'Não foi possível abrir a galeria agora.');
    } finally {
      setIsPickingAvatar(false);
    }
  }

  async function handleSaveName() {
    if (isSavingProfile || isChangingPassword || isDeletingAccount) {
      return;
    }

    const nextName = profileNameDraft.trim();

    if (!nextName) {
      pushProfileStatus('error', 'Informe um nome para o perfil.');
      return;
    }

    setIsSavingProfile(true);

    try {
      const updatedUser = await updateMyProfile(accessToken, {
        full_name: nextName,
      });
      setProfileNameDraft(updatedUser.full_name?.trim() || nextName);
      pushProfileStatus('success', 'Nome atualizado na conta.');
    } catch {
      pushProfileStatus('error', 'Não foi possível salvar o nome.');
    } finally {
      setIsSavingProfile(false);
    }
  }

  async function handleSavePhone() {
    if (isSavingProfile || isChangingPassword || isDeletingAccount) {
      return;
    }

    const digits = profilePhoneDraft.replace(/\D/g, '');

    if (digits.length !== 10 && digits.length !== 11) {
      pushProfileStatus(
        'error',
        'Digite um telefone válido com DDD (10 ou 11 dígitos).'
      );
      return;
    }

    setIsSavingProfile(true);

    try {
      const updatedUser = await updateMyProfile(accessToken, {
        phone: digits,
      });

      setProfilePhoneDraft(formatPhone(updatedUser.phone ?? digits));
      pushProfileStatus('success', 'Telefone atualizado na conta.');
    } catch {
      pushProfileStatus('error', 'Não foi possível salvar o telefone.');
    } finally {
      setIsSavingProfile(false);
    }
  }

  async function handleSavePassword() {
    if (isSavingProfile || isChangingPassword || isDeletingAccount) {
      return;
    }

    if (!profileCurrentPassword.trim()) {
      pushProfileStatus('error', 'Informe sua senha atual.');
      return;
    }

    if (profilePassword.length < 8) {
      pushProfileStatus('error', 'A nova senha precisa ter pelo menos 8 caracteres.');
      return;
    }

    if (profilePassword !== profilePasswordConfirmation) {
      pushProfileStatus('error', 'As senhas novas não conferem.');
      return;
    }

    setIsChangingPassword(true);

    try {
      await changeMyPassword(accessToken, {
        current_password: profileCurrentPassword,
        new_password: profilePassword,
      });
      setProfileCurrentPassword('');
      setProfilePassword('');
      setProfilePasswordConfirmation('');
      pushProfileStatus('success', 'Senha atualizada na conta.');
    } catch {
      pushProfileStatus('error', 'Não foi possível alterar sua senha.');
    } finally {
      setIsChangingPassword(false);
    }
  }

  async function handleLogout() {
    await clearSession();
    onLogout();
  }

  return (
    <ScrollView
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.header}>
        <View style={styles.futureHeaderSpace} />
        <Text style={styles.title}>Ajustes do Sistema</Text>
        <Text style={styles.subtitle}>
          Gerencie seu perfil e preferências da conta
        </Text>
      </View>

      <View style={styles.profileSection}>
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Seu perfil</Text>
        </View>

        <View style={styles.profileCard}>
          <View style={styles.profileHeroRow}>
            <View style={styles.profileAvatarWrap}>
              <Image source={profileAvatarSource} style={styles.profileAvatar} />
              <Pressable
                accessibilityRole="button"
                disabled={isSavingProfile || isPickingAvatar || isChangingPassword || isDeletingAccount}
                onPress={handlePickAvatar}
                style={({ pressed }) => [
                  styles.profileAvatarAction,
                  pressed && !isSavingProfile && !isPickingAvatar && styles.pressed,
                  (isSavingProfile || isPickingAvatar || isChangingPassword || isDeletingAccount) && styles.profileActionDisabled,
                ]}
              >
                {isPickingAvatar || isSavingProfile ? <ActivityIndicator color={VARD_COLORS.surface} size="small" /> : <Feather color={VARD_COLORS.surface} name="camera" size={16} />}
              </Pressable>
            </View>

            <View style={styles.profileHeroCopy}>
              <Text style={styles.profileLabel}>Conta principal</Text>
              <Text numberOfLines={1} style={styles.profileHeroName}>
                {trimmedProfileName || initialDisplayName}
              </Text>
              <Text numberOfLines={1} style={styles.profileHeroEmail}>
                {userEmail}
              </Text>
            </View>
          </View>

          <Text style={styles.profileCardHint}>
            Essas ações atualizam a interface agora e ficam prontas para conectar na API depois.
          </Text>

          {profileStatus ? (
            <View
              style={[
                styles.profileStatus,
                profileStatus.tone === 'success' && styles.profileStatusSuccess,
                profileStatus.tone === 'info' && styles.profileStatusInfo,
                profileStatus.tone === 'error' && styles.profileStatusError,
              ]}
            >
              <Feather
                color={profileStatus.tone === 'error' ? '#B42318' : profileStatus.tone === 'info' ? VARD_COLORS.secondary : '#067647'}
                name={profileStatus.tone === 'error' ? 'alert-triangle' : profileStatus.tone === 'info' ? 'info' : 'check-circle'}
                size={16}
              />
              <Text style={[styles.profileStatusText, profileStatus.tone === 'error' && styles.profileStatusTextError, profileStatus.tone === 'info' && styles.profileStatusTextInfo, profileStatus.tone === 'success' && styles.profileStatusTextSuccess]}>
                {profileStatus.message}
              </Text>
            </View>
          ) : null}
        </View>

        <View style={styles.profileActionCard}>
          <View style={styles.profileActionHeader}>
            <View style={styles.profileActionIconWrap}>
              <Feather color={VARD_COLORS.primary} name="image" size={18} />
            </View>
            <View style={styles.profileActionCopy}>
              <Text style={styles.profileActionTitle}>Foto de perfil</Text>
              <Text style={styles.profileActionDescription}>Troque a imagem do avatar e veja a prévia imediatamente.</Text>
            </View>
          </View>

          <Pressable
            accessibilityRole="button"
            disabled={isSavingProfile || isChangingPassword || isDeletingAccount}
            onPress={handlePickAvatar}
            style={({ pressed }) => [
              styles.profileActionButton,
              pressed && !isSavingProfile && styles.pressed,
              (isSavingProfile || isChangingPassword || isDeletingAccount) && styles.profileActionDisabled,
            ]}
          >
            <Text style={styles.profileActionButtonText}>{isSavingProfile ? 'Salvando...' : 'Escolher foto'}</Text>
          </Pressable>
        </View>

        <View style={styles.profileActionCard}>
          <View style={styles.profileActionHeader}>
            <View style={styles.profileActionIconWrap}>
              <Feather color={VARD_COLORS.primary} name="phone" size={18} />
            </View>
            <View style={styles.profileActionCopy}>
              <Text style={styles.profileActionTitle}>Telefone</Text>
              <Text style={styles.profileActionDescription}>Adicione um número para contato e recuperação da conta.</Text>
            </View>
          </View>

          <TextInput
            autoCapitalize="none"
            keyboardType="phone-pad"
            placeholder="(00) 00000-0000"
            placeholderTextColor="#98A2B3"
            style={styles.profileInput}
            value={profilePhoneDraft}
            onChangeText={(text) => {
              setProfilePhoneDraft(formatPhone(text));
            }}
            maxLength={15}
          />

          <Pressable
            accessibilityRole="button"
            disabled={isSavingProfile || isChangingPassword || isDeletingAccount}
            onPress={handleSavePhone}
            style={({ pressed }) => [
              styles.profileActionButton,
              pressed && !isSavingProfile && styles.pressed,
              (isSavingProfile || isChangingPassword || isDeletingAccount) && styles.profileActionDisabled,
            ]}
          >
            <Text style={styles.profileActionButtonText}>{isSavingProfile ? 'Salvando...' : 'Salvar telefone'}</Text>
          </Pressable>
        </View>

        <View style={styles.profileActionCard}>
          <View style={styles.profileActionHeader}>
            <View style={styles.profileActionIconWrap}>
                <Feather color={VARD_COLORS.primary} name="user" size={18} />
            </View>
            <View style={styles.profileActionCopy}>
                <Text style={styles.profileActionTitle}>Nome de usuário</Text>
                <Text style={styles.profileActionDescription}>Edite o nome exibido nos módulos do app.</Text>
            </View>
          </View>

          <TextInput
            autoCapitalize="words"
            placeholder="Digite seu nome"
            placeholderTextColor="#98A2B3"
            style={styles.profileInput}
            value={profileNameDraft}
            onChangeText={setProfileNameDraft}
          />

          <Pressable
            accessibilityRole="button"
            disabled={isSavingProfile || isChangingPassword || isDeletingAccount}
            onPress={handleSaveName}
            style={({ pressed }) => [
              styles.profileActionButton,
              pressed && !isSavingProfile && styles.pressed,
              (isSavingProfile || isChangingPassword || isDeletingAccount) && styles.profileActionDisabled,
            ]}
          >
            <Text style={styles.profileActionButtonText}>{isSavingProfile ? 'Salvando...' : 'Salvar nome'}</Text>
          </Pressable>
        </View>

        <View style={styles.profileActionCard}>
          <View style={styles.profileActionHeader}>
            <View style={styles.profileActionIconWrap}>
              <Feather color={VARD_COLORS.primary} name="lock" size={18} />
            </View>
            <View style={styles.profileActionCopy}>
              <Text style={styles.profileActionTitle}>Senha</Text>
              <Text style={styles.profileActionDescription}>Prepare a alteração da senha com confirmação visual.</Text>
            </View>
          </View>

          <TextInput
            autoCapitalize="none"
            placeholder="Senha atual"
            placeholderTextColor="#98A2B3"
            secureTextEntry
            style={styles.profileInput}
            value={profileCurrentPassword}
            onChangeText={setProfileCurrentPassword}
          />
          <TextInput
            autoCapitalize="none"
            placeholder="Nova senha"
            placeholderTextColor="#98A2B3"
            secureTextEntry
            style={styles.profileInput}
            value={profilePassword}
            onChangeText={setProfilePassword}
          />
          <TextInput
            autoCapitalize="none"
            placeholder="Confirmar nova senha"
            placeholderTextColor="#98A2B3"
            secureTextEntry
            style={styles.profileInput}
            value={profilePasswordConfirmation}
            onChangeText={setProfilePasswordConfirmation}
          />

          <Pressable
            accessibilityRole="button"
            disabled={isChangingPassword || isSavingProfile || isDeletingAccount}
            onPress={handleSavePassword}
            style={({ pressed }) => [
              styles.profileActionButton,
              pressed && !isChangingPassword && styles.pressed,
              (isSavingProfile || isChangingPassword || isDeletingAccount) && styles.profileActionDisabled,
            ]}
          >
            <Text style={styles.profileActionButtonText}>{isChangingPassword ? 'Salvando...' : 'Salvar senha'}</Text>
          </Pressable>
        </View>
      </View>

      <View style={styles.accountSection}>
        <Pressable
          accessibilityRole="button"
          onPress={handleLogout}
          style={styles.logoutButton}
        >
          <Feather color="#B42318" name="log-out" size={18} />
          <Text style={styles.logoutButtonText}>Sair da conta</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingHorizontal: 22,
    paddingTop: 24,
    paddingBottom: 144,
  },
  header: {
    marginBottom: 28,
  },
  futureHeaderSpace: {
    height: 56,
  },
  title: {
    color: VARD_COLORS.primary,
    fontFamily: SETTINGS_PANEL_FONTS.extraBold,
    fontSize: 22,
    lineHeight: 28,
  },
  subtitle: {
    marginTop: 4,
    color: VARD_COLORS.muted,
    fontFamily: SETTINGS_PANEL_FONTS.regular,
    fontSize: 14,
    lineHeight: 20,
  },
  workspaceName: {
    marginTop: 10,
    color: VARD_COLORS.text,
    fontFamily: SETTINGS_PANEL_FONTS.bold,
    fontSize: 13,
  },
  profileSection: {
    marginBottom: 30,
    gap: 14,
  },
  centerState: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 72,
    gap: 10,
  },
  centerStateText: {
    color: VARD_COLORS.muted,
    fontFamily: SETTINGS_PANEL_FONTS.regular,
    fontSize: 14,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  sectionTitle: {
    color: VARD_COLORS.text,
    fontFamily: SETTINGS_PANEL_FONTS.bold,
    fontSize: 18,
    lineHeight: 24,
  },
  profileCard: {
    borderRadius: 24,
    backgroundColor: VARD_COLORS.surface,
    padding: 18,
    shadowColor: VARD_COLORS.text,
    shadowOpacity: 0.06,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 10 },
    elevation: 2,
    gap: 14,
  },
  profileHeroRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
  },
  profileAvatarWrap: {
    width: 84,
    height: 84,
    alignItems: 'center',
    justifyContent: 'center',
  },
  profileAvatar: {
    width: 84,
    height: 84,
    borderRadius: 28,
    backgroundColor: '#E4E7EC',
  },
  profileAvatarAction: {
    position: 'absolute',
    right: -2,
    bottom: -2,
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 999,
    backgroundColor: VARD_COLORS.primary,
    borderWidth: 2,
    borderColor: VARD_COLORS.surface,
  },
  profileHeroCopy: {
    flex: 1,
  },
  profileLabel: {
    color: VARD_COLORS.primary,
    fontFamily: SETTINGS_PANEL_FONTS.semiBold,
    fontSize: 12,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  profileHeroName: {
    marginTop: 4,
    color: VARD_COLORS.text,
    fontFamily: SETTINGS_PANEL_FONTS.extraBold,
    fontSize: 20,
    lineHeight: 26,
  },
  profileHeroEmail: {
    marginTop: 4,
    color: VARD_COLORS.muted,
    fontFamily: SETTINGS_PANEL_FONTS.regular,
    fontSize: 13,
    lineHeight: 18,
  },
  profileCardHint: {
    color: VARD_COLORS.muted,
    fontFamily: SETTINGS_PANEL_FONTS.regular,
    fontSize: 13,
    lineHeight: 19,
  },
  profileStatus: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  profileStatusSuccess: {
    backgroundColor: '#ECFDF3',
  },
  profileStatusInfo: {
    backgroundColor: VARD_COLORS.secondarySoft,
  },
  profileStatusError: {
    backgroundColor: '#FEF3F2',
  },
  profileStatusText: {
    flex: 1,
    fontFamily: SETTINGS_PANEL_FONTS.semiBold,
    fontSize: 13,
    lineHeight: 18,
  },
  profileStatusTextSuccess: {
    color: '#067647',
  },
  profileStatusTextInfo: {
    color: VARD_COLORS.secondary,
  },
  profileStatusTextError: {
    color: '#B42318',
  },
  profileActionCard: {
    borderRadius: 22,
    backgroundColor: VARD_COLORS.surface,
    padding: 18,
    shadowColor: VARD_COLORS.text,
    shadowOpacity: 0.05,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 8 },
    elevation: 2,
    gap: 12,
  },
  profileActionHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
  },
  profileActionIconWrap: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
    backgroundColor: VARD_COLORS.primarySoft,
  },
  profileActionCopy: {
    flex: 1,
  },
  profileActionTitle: {
    color: VARD_COLORS.text,
    fontFamily: SETTINGS_PANEL_FONTS.bold,
    fontSize: 15,
  },
  profileActionDescription: {
    marginTop: 4,
    color: VARD_COLORS.muted,
    fontFamily: SETTINGS_PANEL_FONTS.regular,
    fontSize: 13,
    lineHeight: 18,
  },
  profileInput: {
    minHeight: 50,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#D0D5DD',
    backgroundColor: '#F9FAFB',
    paddingHorizontal: 14,
    color: VARD_COLORS.text,
    fontFamily: SETTINGS_PANEL_FONTS.regular,
    fontSize: 14,
  },
  profileActionButton: {
    minHeight: 48,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 14,
    backgroundColor: VARD_COLORS.primary,
    paddingHorizontal: 16,
  },
  profileActionDisabled: {
    opacity: 0.65,
  },
  profileActionButtonText: {
    color: VARD_COLORS.surface,
    fontFamily: SETTINGS_PANEL_FONTS.bold,
    fontSize: 14,
  },
  pressed: {
    opacity: 0.78,
  },
  accountSection: {
    marginTop: 24,
    paddingTop: 18,
    borderTopWidth: 1,
    borderTopColor: '#EAECF0',
  },
  logoutButton: {
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#FDA29B',
    backgroundColor: VARD_COLORS.surface,
  },
  logoutButtonText: {
    color: '#B42318',
    fontFamily: SETTINGS_PANEL_FONTS.bold,
    fontSize: 14,
  },
  deleteAccountButton: {
    minHeight: 48,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#FDA29B',
    backgroundColor: '#FFF5F5',
    paddingHorizontal: 16,
  },
  deleteAccountButtonDisabled: {
    opacity: 0.7,
  },
  deleteAccountButtonText: {
    color: '#B42318',
    fontFamily: SETTINGS_PANEL_FONTS.bold,
    fontSize: 14,
  },
});
