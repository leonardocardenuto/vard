import { VARD_COLORS } from '../../../theme/vardTheme';
import { StyleSheet } from 'react-native';

const SETTINGS_FONTS = {
  regular: 'Poppins-Regular',
  semiBold: 'Poppins-SemiBold',
  bold: 'Poppins-Bold',
  extraBold: 'Poppins-ExtraBold',
} as const;

export const styles = StyleSheet.create({
  flex: {
    flex: 1,
  },
  content: {
    paddingHorizontal: 22,
    paddingBottom: 144,
  },
  topSpacer: {
    height: 56,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  backButton: {
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: {
    color: VARD_COLORS.text,
    fontFamily: SETTINGS_FONTS.extraBold,
    fontSize: 22,
  },
  subtitle: {
    marginTop: 8,
    marginBottom: 22,
    color: VARD_COLORS.muted,
    fontFamily: SETTINGS_FONTS.regular,
    fontSize: 14,
    lineHeight: 20,
  },
  section: {
    marginBottom: 18,
    padding: 16,
    borderRadius: 20,
    backgroundColor: VARD_COLORS.surface,
    shadowColor: VARD_COLORS.text,
    shadowOpacity: 0.05,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 8 },
    elevation: 2,
  },
  sectionTitle: {
    color: VARD_COLORS.text,
    fontFamily: SETTINGS_FONTS.bold,
    fontSize: 16,
    marginBottom: 12,
  },
  protocolCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    backgroundColor: '#FCFCFD',
    marginBottom: 10,
  },
  protocolCardActive: {
    borderColor: VARD_COLORS.primary,
    backgroundColor: VARD_COLORS.primarySoft,
  },
  protocolTextWrap: {
    flex: 1,
    paddingRight: 12,
  },
  protocolLabel: {
    color: VARD_COLORS.text,
    fontFamily: SETTINGS_FONTS.bold,
    fontSize: 15,
  },
  protocolDescription: {
    color: VARD_COLORS.muted,
    fontFamily: SETTINGS_FONTS.regular,
    fontSize: 13,
    lineHeight: 18,
    marginTop: 4,
  },
  radioOuter: {
    width: 20,
    height: 20,
    borderRadius: 999,
    borderWidth: 2,
    borderColor: '#D0D5DD',
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioOuterActive: {
    borderColor: VARD_COLORS.primary,
  },
  radioInner: {
    width: 8,
    height: 8,
    borderRadius: 999,
    backgroundColor: VARD_COLORS.primary,
  },
  input: {
    minHeight: 48,
    borderRadius: 14,
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: '#E5E7EB',
    paddingHorizontal: 14,
    color: VARD_COLORS.text,
    fontFamily: SETTINGS_FONTS.regular,
    fontSize: 14,
    marginBottom: 10,
  },
  multilineInput: {
    minHeight: 88,
    paddingTop: 14,
  },
  errorText: {
    marginBottom: 14,
    color: '#B42318',
    fontFamily: SETTINGS_FONTS.semiBold,
    fontSize: 13,
    lineHeight: 18,
  },
  primaryButton: {
    minHeight: 50,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: VARD_COLORS.primary,
  },
  buttonDisabled: {
    opacity: 0.7,
  },
  primaryButtonText: {
    color: VARD_COLORS.surface,
    fontFamily: SETTINGS_FONTS.extraBold,
    fontSize: 15,
  },
});
