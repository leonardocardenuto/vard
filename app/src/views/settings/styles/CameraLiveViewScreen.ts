import { StyleSheet } from 'react-native';

const LIVE_VIEW_FONTS = {
  regular: 'Poppins-Regular',
  extraBold: 'Poppins-ExtraBold',
} as const;

export const styles = StyleSheet.create({
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
    marginBottom: 18,
  },
  backButton: {
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerText: {
    flex: 1,
  },
  headerTitle: {
    color: '#111827',
    fontFamily: LIVE_VIEW_FONTS.extraBold,
    fontSize: 22,
  },
  headerSubtitle: {
    marginTop: 4,
    color: '#667085',
    fontFamily: LIVE_VIEW_FONTS.regular,
    fontSize: 14,
  },
  viewerCard: {
    overflow: 'hidden',
    borderRadius: 20,
    backgroundColor: '#09131F',
    height: 520,
  },
  video: {
    width: '100%',
    height: '100%',
  },
  webview: {
    width: '100%',
    height: '100%',
    backgroundColor: '#000000',
  },
});
