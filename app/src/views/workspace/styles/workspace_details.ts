import { StyleSheet } from 'react-native';

const WORKSPACE_DETAILS_FONTS = {
  regular: 'Poppins-Regular',
  medium: 'Poppins-Medium',
  semiBold: 'Poppins-SemiBold',
  bold: 'Poppins-Bold',
} as const;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5F7FA',
  },
  content: {
    paddingHorizontal: 20,
    paddingTop: 22,
    paddingBottom: 144,
  },
  headerRow: {
    alignItems: 'center',
    flexDirection: 'row',
    marginBottom: 12,
  },
  backButton: {
    alignItems: 'center',
    height: 36,
    justifyContent: 'center',
    marginRight: 8,
    width: 36,
  },
  title: {
    color: '#101828',
    fontFamily: WORKSPACE_DETAILS_FONTS.bold,
    fontSize: 24,
    marginTop: 8,
  },
  subtitle: {
    color: '#777777',
    fontFamily: WORKSPACE_DETAILS_FONTS.regular,
    marginBottom: 15,
    marginTop: 2,
  },
  alertCard: {
    backgroundColor: '#FDECEA',
    borderColor: '#E74C3C',
    borderRadius: 15,
    borderWidth: 1,
    marginBottom: 20,
    padding: 15,
  },
  alertHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    marginBottom: 10,
  },
  alertTitle: {
    color: '#C0392B',
    fontFamily: WORKSPACE_DETAILS_FONTS.bold,
  },
  alertSubtitle: {
    color: '#555555',
    fontFamily: WORKSPACE_DETAILS_FONTS.regular,
  },
  secondaryButton: {
    backgroundColor: '#FFFFFF',
    borderRadius: 10,
    marginVertical: 5,
    padding: 12,
  },
  secondaryText: {
    color: '#C0392B',
    fontFamily: WORKSPACE_DETAILS_FONTS.bold,
    textAlign: 'center',
  },
  primaryButton: {
    backgroundColor: '#E74C3C',
    borderRadius: 10,
    padding: 12,
  },
  primaryText: {
    color: '#FFFFFF',
    fontFamily: WORKSPACE_DETAILS_FONTS.bold,
    textAlign: 'center',
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  sectionTitle: {
    color: '#101828',
    fontFamily: WORKSPACE_DETAILS_FONTS.bold,
    fontSize: 16,
  },
  live: {
    color: '#00A8CC',
    fontFamily: WORKSPACE_DETAILS_FONTS.regular,
    fontSize: 12,
  },
  activityCard: {
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    flexDirection: 'row',
    marginBottom: 10,
    padding: 15,
  },
  snapshotCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    marginBottom: 20,
    padding: 15,
  },
  snapshotHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    marginBottom: 10,
  },
  imageRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  snapshotImage: {
    borderRadius: 10,
    height: 100,
    width: '48%',
  },
  caregivers: {
    flexDirection: 'row',
    marginBottom: 28,
    marginTop: 12,
  },
  person: {
    alignItems: 'center',
    marginRight: 15,
  },
  personImage: {
    borderRadius: 25,
    height: 50,
    marginBottom: 5,
    width: 50,
  },
  personName: {
    color: '#101828',
    fontFamily: WORKSPACE_DETAILS_FONTS.semiBold,
    fontSize: 13,
  },
  addPerson: {
    alignItems: 'center',
    borderColor: '#9AA8BA',
    borderRadius: 25,
    borderStyle: 'dashed',
    borderWidth: 1,
    height: 50,
    justifyContent: 'center',
    width: 82,
  },
  addPersonIcon: {
    fontSize: 20,
    lineHeight: 22,
  },
  addPersonText: {
    color: '#667085',
    fontFamily: WORKSPACE_DETAILS_FONTS.regular,
    fontSize: 12,
  },
  activityText: {
    color: '#101828',
    fontFamily: WORKSPACE_DETAILS_FONTS.medium,
  },
  time: {
    color: '#777777',
    fontFamily: WORKSPACE_DETAILS_FONTS.regular,
    fontSize: 12,
  },
  mutedText: {
    color: '#667085',
    fontFamily: WORKSPACE_DETAILS_FONTS.regular,
    fontSize: 13,
    lineHeight: 18,
    marginTop: 8,
  },
  pressed: {
    opacity: 0.7,
  },
  errorText: {
    color: '#B42318',
    fontFamily: WORKSPACE_DETAILS_FONTS.bold,
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 12,
  },
});

export { styles };
