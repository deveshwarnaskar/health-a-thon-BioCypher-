import React, { useEffect, useState } from "react";
import {
  Modal,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  ActivityIndicator,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, typography } from "../../theming/tokens";
import { useVoiceRecorder } from "../../services/voice/useVoiceRecorder";

export type VoiceRecordModalProps = {
  visible: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  placeholderHint?: string;
  onTranscribeSuccess: (transcript: string) => void;
  testID?: string;
};

export function VoiceRecordModal({
  visible,
  onClose,
  title,
  subtitle,
  placeholderHint,
  onTranscribeSuccess,
  testID,
}: VoiceRecordModalProps) {
  const {
    status,
    durationSeconds,
    error,
    isRecording,
    isTranscribing,
    isVoiceAvailable,
    startRecording,
    stopAndTranscribe,
    cancelRecording,
    reset,
  } = useVoiceRecorder();

  const [hasStartedOnce, setHasStartedOnce] = useState(false);

  useEffect(() => {
    if (!visible) {
      cancelRecording();
      setHasStartedOnce(false);
    }
  }, [visible, cancelRecording]);

  const handleStart = async () => {
    setHasStartedOnce(true);
    await startRecording();
  };

  const handleStop = async () => {
    const transcript = await stopAndTranscribe();
    if (transcript && transcript.trim().length > 0) {
      onTranscribeSuccess(transcript.trim());
      onClose();
    }
  };

  const handleCancel = async () => {
    await cancelRecording();
    onClose();
  };

  const formatTimer = (totalSec: number) => {
    const mins = Math.floor(totalSec / 60);
    const secs = totalSec % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={handleCancel}
      testID={testID}
    >
      <View style={styles.overlay}>
        <View style={styles.modalCard}>
          {/* Header */}
          <View style={styles.headerRow}>
            <View style={styles.headerTitles}>
              <Text style={styles.title} allowFontScaling numberOfLines={1}>
                {title}
              </Text>
              {subtitle ? (
                <Text style={styles.subtitle} allowFontScaling numberOfLines={2}>
                  {subtitle}
                </Text>
              ) : null}
            </View>
            <TouchableOpacity
              style={styles.closeBtn}
              onPress={handleCancel}
              accessibilityRole="button"
              accessibilityLabel="Close voice modal"
            >
              <Ionicons name="close" size={20} color="#64748B" />
            </TouchableOpacity>
          </View>

          {/* Central Recording State */}
          <View style={styles.centerSection}>
            {isTranscribing ? (
              <View style={styles.transcribingState}>
                <ActivityIndicator size="large" color="#0D9488" />
                <Text style={styles.transcribingText} allowFontScaling>
                  Processing voice with AI…
                </Text>
                <Text style={styles.transcribingSubtext} allowFontScaling>
                  Transcribing your audio dictation
                </Text>
              </View>
            ) : isRecording ? (
              <View style={styles.recordingState}>
                <View style={styles.recordingPulseOuter}>
                  <TouchableOpacity
                    style={styles.recordingMicActive}
                    onPress={handleStop}
                    accessibilityRole="button"
                    accessibilityLabel="Stop recording"
                  >
                    <Ionicons name="stop" size={28} color="#FFFFFF" />
                  </TouchableOpacity>
                </View>
                <View style={styles.timerBadge}>
                  <View style={styles.recordingRedDot} />
                  <Text style={styles.timerText} allowFontScaling>
                    {formatTimer(durationSeconds)}
                  </Text>
                </View>
                <Text style={styles.instructionText} allowFontScaling>
                  Listening… Tap square to finish
                </Text>
              </View>
            ) : !isVoiceAvailable ? (
              <View style={styles.idleState}>
                <View
                  style={[styles.idleMicBtn, { backgroundColor: "#94A3B8" }]}
                >
                  <Ionicons name="mic-off" size={32} color="#FFFFFF" />
                </View>
                <Text style={styles.idleActionPrompt} allowFontScaling>
                  Voice Recording Unavailable
                </Text>
                <Text style={styles.hintText} allowFontScaling>
                  Native audio recording module is not available in this Expo Go build. Please use manual entry or test in a development client.
                </Text>
              </View>
            ) : (
              <View style={styles.idleState}>
                <TouchableOpacity
                  style={styles.idleMicBtn}
                  onPress={handleStart}
                  accessibilityRole="button"
                  accessibilityLabel="Tap to record voice"
                >
                  <Ionicons name="mic" size={32} color="#FFFFFF" />
                </TouchableOpacity>
                <Text style={styles.idleActionPrompt} allowFontScaling>
                  Tap the microphone to speak
                </Text>
                {placeholderHint ? (
                  <Text style={styles.hintText} allowFontScaling>
                    “{placeholderHint}”
                  </Text>
                ) : null}
              </View>
            )}

            {/* Error Notice */}
            {error ? (
              <View style={styles.errorBanner}>
                <Ionicons name="alert-circle" size={16} color="#DC2626" style={{ marginRight: 6 }} />
                <Text style={styles.errorText} allowFontScaling>
                  {error}
                </Text>
              </View>
            ) : null}
          </View>

          {/* Footer Actions */}
          <View style={styles.footerRow}>
            {isRecording ? (
              <TouchableOpacity
                style={styles.doneBtn}
                onPress={handleStop}
                accessibilityRole="button"
                accessibilityLabel="Finish and transcribe"
              >
                <Ionicons name="checkmark-circle" size={18} color="#FFFFFF" style={{ marginRight: 6 }} />
                <Text style={styles.doneBtnText} allowFontScaling>
                  Done & Transcribe
                </Text>
              </TouchableOpacity>
            ) : null}

            <TouchableOpacity
              style={isRecording ? styles.cancelSmallBtn : styles.cancelFullBtn}
              onPress={handleCancel}
              accessibilityRole="button"
              accessibilityLabel="Cancel recording"
            >
              <Text style={styles.cancelBtnText} allowFontScaling>
                Cancel
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.65)",
    justifyContent: "flex-end",
  },
  modalCard: {
    backgroundColor: "#FFFFFF",
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.xl,
    gap: spacing.md,
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.12,
    shadowRadius: 20,
    elevation: 10,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
  },
  headerTitles: {
    flex: 1,
    paddingRight: spacing.sm,
  },
  title: {
    fontSize: 19,
    fontWeight: "800",
    color: "#0F172A",
    letterSpacing: -0.4,
  },
  subtitle: {
    fontSize: 13,
    color: "#64748B",
    marginTop: 2,
    lineHeight: 18,
  },
  closeBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: "#F1F5F9",
    alignItems: "center",
    justifyContent: "center",
  },
  centerSection: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.md,
    gap: spacing.md,
  },
  idleState: {
    alignItems: "center",
    gap: 10,
  },
  idleMicBtn: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: "#0D9488",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#0D9488",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.35,
    shadowRadius: 14,
    elevation: 6,
  },
  idleActionPrompt: {
    fontSize: 15,
    fontWeight: "700",
    color: "#0F172A",
    marginTop: 4,
  },
  hintText: {
    fontSize: 12,
    color: "#64748B",
    fontStyle: "italic",
    textAlign: "center",
    paddingHorizontal: spacing.md,
  },
  recordingState: {
    alignItems: "center",
    gap: 12,
  },
  recordingPulseOuter: {
    width: 84,
    height: 84,
    borderRadius: 42,
    backgroundColor: "#FEE2E2",
    alignItems: "center",
    justifyContent: "center",
  },
  recordingMicActive: {
    width: 68,
    height: 68,
    borderRadius: 34,
    backgroundColor: "#EF4444",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#EF4444",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 12,
    elevation: 6,
  },
  timerBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FEF2F2",
    borderWidth: 1,
    borderColor: "#FECACA",
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: radii.pill,
    gap: 6,
  },
  recordingRedDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#EF4444",
  },
  timerText: {
    fontSize: 14,
    fontWeight: "800",
    color: "#DC2626",
    fontVariant: ["tabular-nums"],
  },
  instructionText: {
    fontSize: 13,
    color: "#475569",
    fontWeight: "600",
  },
  transcribingState: {
    alignItems: "center",
    paddingVertical: spacing.md,
    gap: 8,
  },
  transcribingText: {
    fontSize: 15,
    fontWeight: "700",
    color: "#0F172A",
  },
  transcribingSubtext: {
    fontSize: 12,
    color: "#64748B",
  },
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FEF2F2",
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#FECACA",
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginHorizontal: spacing.sm,
  },
  errorText: {
    fontSize: 12,
    color: "#DC2626",
    flex: 1,
    fontWeight: "600",
  },
  footerRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  doneBtn: {
    flex: 2,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#0D9488",
    paddingVertical: 14,
    borderRadius: 14,
    shadowColor: "#0D9488",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 3,
  },
  doneBtnText: {
    fontSize: 15,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  cancelSmallBtn: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#F1F5F9",
    paddingVertical: 14,
    borderRadius: 14,
  },
  cancelFullBtn: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    paddingVertical: 14,
    borderRadius: 14,
  },
  cancelBtnText: {
    fontSize: 14,
    fontWeight: "700",
    color: "#475569",
  },
});
