import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Image,
  Keyboard,
  LayoutAnimation,
  Modal,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { colors, radii, spacing, touchTarget, typography } from "../../../theming/tokens";
import { useConnectivity } from "../../../connectivity/useConnectivity";
import { useIngestGlucose } from "../../glucose/useIngestGlucose";
import { useLogMeal } from "../../meals/useLogMeal";
import { useSarvamChat, useSarvamMealAnalysis } from "../api";
import { secureUuid } from "../../../services/api/correlation";
import type { AnalyzeMealAiResponse, AnalyzeMealPhotoAiResponse } from "../../../services/schemas/ai";
import type { ReadingTag } from "../../glucose/types";
import { VoiceRecordModal } from "../../../components/voice/VoiceRecordModal";
import { MealPhotoModal } from "../../../components/camera/MealPhotoModal";

export type ThaliAssistModalProps = {
  visible: boolean;
  onClose: () => void;
  onNavigateToRecords?: () => void;
  onNavigateToMeal?: () => void;
  onNavigateToReports?: () => void;
  patientId?: string | null;
  patientName?: string;
};

type AssistTopic = "today" | "meal" | "appointment" | "voice" | "ai_chat" | "summarize_week" | null;

type AiChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  imageUri?: string;
  mealData?: AnalyzeMealAiResponse | AnalyzeMealPhotoAiResponse;
  isEmergency?: boolean;
};

type VoiceDraft =
  | {
      kind: "glucose";
      rawText: string;
      value: number;
      tag?: ReadingTag;
      missingTag: boolean;
    }
  | {
      kind: "meal";
      rawText: string;
      description: string;
      mealType?: "breakfast" | "lunch" | "dinner" | "snack";
      missingMealType: boolean;
    }
  | null;

export function ThaliAssistModal({
  visible,
  onClose,
  onNavigateToRecords,
  onNavigateToMeal,
  onNavigateToReports,
  patientId,
  patientName = "",
}: ThaliAssistModalProps) {
  const { isOffline } = useConnectivity();
  const insets = useSafeAreaInsets();
  const [selectedTopic, setSelectedTopic] = useState<AssistTopic>(null);
  const [voiceInput, setVoiceInput] = useState("");
  const [voiceDraft, setVoiceDraft] = useState<VoiceDraft>(null);
  const [voiceSaveSuccess, setVoiceSaveSuccess] = useState<string | null>(null);
  const [voiceError, setVoiceError] = useState<string | null>(null);

  const ingestGlucose = useIngestGlucose({ patientId });
  const logMeal = useLogMeal({ patientId });
  const isSaving = ingestGlucose.isPending || logMeal.isPending;

  const sarvamChat = useSarvamChat();
  const sarvamMeal = useSarvamMealAnalysis();
  const [aiQuery, setAiQuery] = useState("");
  const [aiMessages, setAiMessages] = useState<AiChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      text: "Namaste! Main aapka THALI Indic AI companion hoon. Aap mujhse khane-peene ke sawal (jaise 'Can I eat mango?'), meal nutrition analysis, ya sugar ke baare mein pooch sakte hain.",
    },
  ]);
  const [isAiLoading, setIsAiLoading] = useState(false);

  // Modals for AI Voice & Camera
  const [isAiVoiceModalVisible, setIsAiVoiceModalVisible] = useState(false);
  const [isAiCameraModalVisible, setIsAiCameraModalVisible] = useState(false);
  const [isDirectVoiceModalVisible, setIsDirectVoiceModalVisible] = useState(false);
  const chatScrollRef = useRef<ScrollView>(null);

  // Accurate native keyboard height tracking
  const [keyboardHeight, setKeyboardHeight] = useState(0);

  useEffect(() => {
    const showEvent = Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow";
    const hideEvent = Platform.OS === "ios" ? "keyboardWillHide" : "keyboardDidHide";

    const onShow = (e: any) => {
      const height = e?.endCoordinates?.height ?? 0;
      if (Platform.OS === "ios") {
        LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
      }
      setKeyboardHeight(height);
      setTimeout(() => {
        chatScrollRef.current?.scrollToEnd({ animated: true });
      }, 50);
    };

    const onHide = () => {
      if (Platform.OS === "ios") {
        LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
      }
      setKeyboardHeight(0);
    };

    const showSub = Keyboard.addListener(showEvent, onShow);
    const hideSub = Keyboard.addListener(hideEvent, onHide);

    return () => {
      showSub.remove();
      hideSub.remove();
    };
  }, []);

  useEffect(() => {
    if (selectedTopic === "ai_chat") {
      const timer = setTimeout(() => {
        chatScrollRef.current?.scrollToEnd({ animated: true });
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [aiMessages.length, isAiLoading, selectedTopic]);

  const handleReceivePhotoAnalysis = (
    result: AnalyzeMealPhotoAiResponse,
    photoUri: string
  ) => {
    const userMsgId = secureUuid();
    const assistantMsgId = secureUuid();

    setAiMessages((prev) => [
      ...prev,
      {
        id: userMsgId,
        role: "user",
        text: result.description ? `Uploaded meal photo: ${result.description}` : "Uploaded meal photo for analysis",
        imageUri: photoUri,
      },
      {
        id: assistantMsgId,
        role: "assistant",
        text:
          result.patient_guidance_hinglish ||
          `Meal analyzed with ICMR-NIN nutrition data. Glycemic impact: ${result.glycemic_impact || "MODERATE"}.`,
        mealData: result,
      },
    ]);
  };

  const handleSendAi = async (customText?: string) => {
    const textToSend = (customText ?? aiQuery).trim();
    if (!textToSend || isAiLoading) return;

    const userMsgId = secureUuid();
    setAiMessages((prev) => [...prev, { id: userMsgId, role: "user", text: textToSend }]);
    setAiQuery("");
    setIsAiLoading(true);

    try {
      const isFoodAnalysis =
        /\b(analyze|roti|rice|chawal|dal|sabzi|dosa|idli|paneer|curry|salad|portion|katori|ate|eaten|breakfast|lunch|dinner|snack)\b/i.test(
          textToSend
        ) && !/\b(can i|kya main|safe to|permission)\b/i.test(textToSend);

      if (isFoodAnalysis) {
        const res = await sarvamMeal.mutateAsync({ description: textToSend });
        setAiMessages((prev) => [
          ...prev,
          {
            id: secureUuid(),
            role: "assistant",
            text: res.patient_guidance_hinglish || "Meal analyzed with ICMR-NIN nutrition data.",
            mealData: res,
          },
        ]);
      } else {
        const res = await sarvamChat.mutateAsync({ message: textToSend });
        const isEmergency = /hypoglycemia|rule of 15|dhyan dein|shakkar paani/i.test(res.reply);
        setAiMessages((prev) => [
          ...prev,
          {
            id: secureUuid(),
            role: "assistant",
            text: res.reply,
            isEmergency,
          },
        ]);
      }
    } catch (err: any) {
      setAiMessages((prev) => [
        ...prev,
        {
          id: secureUuid(),
          role: "assistant",
          text: "Maaf kijiye, AI service connect nahi ho paya. Kripya thodi der baad dobara koshish karein.",
        },
      ]);
    } finally {
      setIsAiLoading(false);
    }
  };

  const handleSelectTopic = (topic: AssistTopic) => {
    setSelectedTopic(topic);
    setVoiceDraft(null);
    setVoiceSaveSuccess(null);
    setVoiceError(null);
  };

  const handleParseVoiceInput = (rawText: string) => {
    const text = rawText.trim();
    if (!text) return;

    setVoiceSaveSuccess(null);
    setVoiceError(null);

    const lower = text.toLowerCase();
    const numMatch = lower.match(/\b([4-9]\d|[1-5]\d\d)\b/);
    const hasGlucoseKeyword =
      lower.includes("sugar") ||
      lower.includes("glucose") ||
      lower.includes("fasting") ||
      lower.includes("mg/dl") ||
      lower.includes("reading");

    if (
      numMatch &&
      numMatch[1] &&
      (hasGlucoseKeyword ||
        (!lower.includes("roti") &&
          !lower.includes("rice") &&
          !lower.includes("curry") &&
          !lower.includes("dal") &&
          !lower.includes("ate") &&
          !lower.includes("had")))
    ) {
      const value = parseInt(numMatch[1], 10);
      let tag: ReadingTag | undefined = undefined;
      if (lower.includes("fasting")) {
        tag = "fasting";
      } else if (
        lower.includes("postbreakfast") ||
        (lower.includes("breakfast") && (lower.includes("post") || lower.includes("after")))
      ) {
        tag = "postbreakfast";
      } else if (
        lower.includes("postlunch") ||
        (lower.includes("lunch") && (lower.includes("post") || lower.includes("after")))
      ) {
        tag = "postlunch";
      } else if (
        lower.includes("postdinner") ||
        (lower.includes("dinner") && (lower.includes("post") || lower.includes("after")))
      ) {
        tag = "postdinner";
      } else if (lower.includes("pre") || lower.includes("before")) {
        tag = "premeal";
      } else if (lower.includes("post") || lower.includes("after")) {
        tag = "postlunch";
      }

      setVoiceDraft({
        kind: "glucose",
        rawText: text,
        value,
        tag,
        missingTag: !tag,
      });
      return;
    }

    let mealType: "breakfast" | "lunch" | "dinner" | "snack" | undefined = undefined;
    if (lower.includes("breakfast")) {
      mealType = "breakfast";
    } else if (lower.includes("lunch")) {
      mealType = "lunch";
    } else if (lower.includes("dinner")) {
      mealType = "dinner";
    } else if (lower.includes("snack") || lower.includes("tea")) {
      mealType = "snack";
    }

    setVoiceDraft({
      kind: "meal",
      rawText: text,
      description: text,
      mealType,
      missingMealType: !mealType,
    });
  };

  const handleConfirmAndSave = async () => {
    if (!voiceDraft) return;

    try {
      setVoiceError(null);
      if (voiceDraft.kind === "glucose") {
        await ingestGlucose.mutateAsync({
          value_mg_dl: voiceDraft.value,
          tag: voiceDraft.tag ?? null,
        });
        setVoiceSaveSuccess(`Confirmed and saved glucose reading of ${voiceDraft.value} mg/dL.`);
      } else {
        const desc = voiceDraft.mealType
          ? `${voiceDraft.description} (${voiceDraft.mealType})`
          : voiceDraft.description;
        await logMeal.mutateAsync({
          description: desc,
        });
        setVoiceSaveSuccess(`Confirmed and saved meal: "${voiceDraft.description}".`);
      }
      setVoiceDraft(null);
      setVoiceInput("");
    } catch (err: any) {
      setVoiceError(err?.message || "Failed to save draft. Please try again.");
    }
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <SafeAreaView style={styles.container} edges={["top"]}>
        <View style={styles.header}>
          <View style={styles.headerTitleRow}>
            {selectedTopic === "ai_chat" ? (
              <TouchableOpacity
                style={styles.headerBackBtn}
                onPress={() => setSelectedTopic(null)}
                accessibilityRole="button"
                accessibilityLabel="Back to all topics"
              >
                <Ionicons name="arrow-back" size={20} color="#0D9488" />
              </TouchableOpacity>
            ) : (
              <View style={styles.headerIconBadge}>
                <Ionicons name="sparkles" size={18} color="#0D9488" />
              </View>
            )}
            <View>
              <Text style={styles.title} allowFontScaling>
                {selectedTopic === "ai_chat" ? "Ask THALI AI" : "THALI Assist"}
              </Text>
              <Text style={styles.subtitle} allowFontScaling>
                {selectedTopic === "ai_chat" ? "Sarvam Indic Health Companion" : "Care understanding guide"}
              </Text>
            </View>
          </View>
          <TouchableOpacity
            style={styles.closeButton}
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel="Close THALI Assist"
            activeOpacity={0.7}
          >
            <Ionicons name="close" size={20} color="#0F172A" />
          </TouchableOpacity>
        </View>

        {isOffline ? (
          <View style={styles.offlineNotice} accessibilityRole="alert">
            <Ionicons name="cloud-offline-outline" size={20} color={colors.textSecondary} />
            <Text style={styles.offlineText} allowFontScaling>
              Assist features require an active connection to access your verified clinic records.
            </Text>
          </View>
        ) : null}

        {selectedTopic === "ai_chat" ? (
          <View
            style={[
              styles.aiChatScreen,
              {
                paddingBottom: keyboardHeight > 0 ? keyboardHeight + 20 : Math.max(insets.bottom, 12),
              },
            ]}
          >
            <ScrollView
              ref={chatScrollRef}
              style={styles.aiMessagesScrollView}
              contentContainerStyle={styles.aiMessagesContent}
              keyboardShouldPersistTaps="handled"
              keyboardDismissMode="on-drag"
                onContentSizeChange={() => {
                  chatScrollRef.current?.scrollToEnd({ animated: true });
                }}
              >
                <TouchableOpacity
                  style={{ flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 12 }}
                  onPress={() => setSelectedTopic(null)}
                  accessibilityRole="button"
                  accessibilityLabel="Back to Topics"
                >
                  <Ionicons name="arrow-back" size={18} color={colors.primary} />
                  <Text style={{ fontSize: 14, fontWeight: "600", color: colors.primary }}>All Topics</Text>
                </TouchableOpacity>

                <View style={[styles.provenanceTag, { backgroundColor: "#CCFBF1" }]}>
                  <Text style={[styles.provenanceText, { color: "#0F766E" }]} allowFontScaling>
                    SARVAM AI INDIC HEALTH COMPANION
                  </Text>
                </View>
                <Text style={styles.topicTitle} allowFontScaling>
                  Ask THALI AI
                </Text>
                <Text style={styles.topicBody} allowFontScaling>
                  Chat in English or Hinglish. Ask about Indian foods, meal carb impact, or symptoms. Dictate with microphone or snap photos of your meals! Powered by Sarvam 105B & ICMR-NIN nutrition data.
                </Text>

                {voiceSaveSuccess ? (
                  <View style={styles.voiceSuccessBanner}>
                    <Ionicons name="checkmark-circle" size={16} color="#065F46" style={{ marginRight: 6 }} />
                    <Text style={styles.voiceSuccessText} allowFontScaling>
                      {voiceSaveSuccess}
                    </Text>
                  </View>
                ) : null}

                {voiceError ? (
                  <View style={styles.voiceErrorBanner}>
                    <Ionicons name="alert-circle" size={16} color="#991B1B" style={{ marginRight: 6 }} />
                    <Text style={styles.voiceErrorText} allowFontScaling>
                      {voiceError}
                    </Text>
                  </View>
                ) : null}

                {/* Chat messages */}
                <View style={{ marginTop: 12, gap: 10 }}>
                  {aiMessages.map((msg) => (
                    <View
                      key={msg.id}
                      style={{
                        alignSelf: msg.role === "user" ? "flex-end" : "flex-start",
                        maxWidth: "92%",
                        backgroundColor: msg.role === "user" ? colors.primary : "#F8FAFC",
                        borderRadius: 14,
                        padding: 12,
                        borderWidth: msg.role === "assistant" ? 1 : 0,
                        borderColor: "#E2E8F0",
                      }}
                    >
                      {msg.imageUri ? (
                        <View style={styles.chatImageContainer}>
                          <Image
                            source={{ uri: msg.imageUri }}
                            style={styles.chatThumbnail}
                            resizeMode="cover"
                            accessibilityRole="image"
                            accessibilityLabel="Meal photo"
                          />
                        </View>
                      ) : null}

                      {msg.isEmergency ? (
                        <View style={{ backgroundColor: "#FEE2E2", padding: 10, borderRadius: 8, marginBottom: 8, borderWidth: 1, borderColor: "#FECACA" }}>
                          <View style={{ flexDirection: "row", gap: 6, alignItems: "center", marginBottom: 2 }}>
                            <Ionicons name="warning" size={18} color="#DC2626" />
                            <Text style={{ color: "#991B1B", fontWeight: "700", fontSize: 13 }}>SAFETY ALERT: REPORTED LOW BLOOD GLUCOSE SYMPTOMS</Text>
                          </View>
                          <Text style={{ color: "#7F1D1D", fontSize: 12, lineHeight: 16 }}>
                            You reported symptoms that can occur with low blood glucose. Follow the safety guidance below or contact your doctor immediately.
                          </Text>
                        </View>
                      ) : null}

                      <Text
                        style={{
                          color: msg.role === "user" ? "#FFFFFF" : colors.textPrimary,
                          fontSize: 14,
                          lineHeight: 20,
                        }}
                        allowFontScaling
                      >
                        {msg.text}
                      </Text>

                      {/* Meal nutrition card */}
                      {msg.mealData ? (
                        <View style={{ marginTop: 10, backgroundColor: "#FFFFFF", padding: 10, borderRadius: 8, borderWidth: 1, borderColor: "#CBD5E1" }}>
                          <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: 6 }}>
                            <Text style={{ fontWeight: "700", fontSize: 11, color: "#0F766E" }}>ICMR-NIN NUTRITION BREAKDOWN</Text>
                            <View style={{ backgroundColor: msg.mealData.glycemic_impact === "LOW" ? "#DCFCE7" : msg.mealData.glycemic_impact === "MODERATE" ? "#FEF3C7" : "#FEE2E2", paddingHorizontal: 6, paddingVertical: 1, borderRadius: 4 }}>
                              <Text style={{ fontSize: 10, fontWeight: "700", color: msg.mealData.glycemic_impact === "LOW" ? "#166534" : msg.mealData.glycemic_impact === "MODERATE" ? "#92400E" : "#991B1B" }}>
                                {msg.mealData.glycemic_impact} IMPACT
                              </Text>
                            </View>
                          </View>
                          <View style={{ flexDirection: "row", justifyContent: "space-around", paddingVertical: 4, backgroundColor: "#F8FAFC", borderRadius: 6 }}>
                            <View style={{ alignItems: "center" }}>
                              <Text style={{ fontSize: 11, color: "#64748B" }}>Calories</Text>
                              <Text style={{ fontSize: 13, fontWeight: "700", color: "#1E293B" }}>{Math.round(msg.mealData.total_calories_kcal)} kcal</Text>
                            </View>
                            <View style={{ alignItems: "center" }}>
                              <Text style={{ fontSize: 11, color: "#64748B" }}>Carbs</Text>
                              <Text style={{ fontSize: 13, fontWeight: "700", color: "#1E293B" }}>{Math.round(msg.mealData.total_carbs_g)}g</Text>
                            </View>
                            <View style={{ alignItems: "center" }}>
                              <Text style={{ fontSize: 11, color: "#64748B" }}>Protein</Text>
                              <Text style={{ fontSize: 13, fontWeight: "700", color: "#1E293B" }}>{Math.round(msg.mealData.total_protein_g)}g</Text>
                            </View>
                            <View style={{ alignItems: "center" }}>
                              <Text style={{ fontSize: 11, color: "#64748B" }}>Fiber</Text>
                              <Text style={{ fontSize: 13, fontWeight: "700", color: "#1E293B" }}>{Math.round(msg.mealData.total_fiber_g ?? 0)}g</Text>
                            </View>
                          </View>
                          {((msg.mealData as any)?.raw_description || (msg.mealData as any)?.description) ? (
                            <TouchableOpacity
                              style={{ marginTop: 8, backgroundColor: "#0D9488", paddingVertical: 7, borderRadius: 6, alignItems: "center" }}
                              onPress={async () => {
                                const descToSave = (msg.mealData as any)?.raw_description || (msg.mealData as any)?.description || "Meal";
                                try {
                                  await logMeal.mutateAsync({ description: descToSave });
                                  setVoiceSaveSuccess(`Saved meal: "${descToSave}"`);
                                } catch (e: any) {
                                  setVoiceError("Failed to save meal to log.");
                                }
                              }}
                            >
                              <Text style={{ color: "#FFFFFF", fontWeight: "600", fontSize: 12 }}>+ Save to My Meal Log</Text>
                            </TouchableOpacity>
                          ) : null}
                        </View>
                      ) : null}
                    </View>
                  ))}

                  {isAiLoading ? (
                    <View style={{ flexDirection: "row", alignItems: "center", gap: 8, padding: 12, backgroundColor: "#F8FAFC", borderRadius: 14, alignSelf: "flex-start" }}>
                      <ActivityIndicator size="small" color="#0D9488" />
                      <Text style={{ fontSize: 13, color: "#64748B" }}>THALI AI is thinking...</Text>
                    </View>
                  ) : null}
                </View>

                {/* Sample quick prompts */}
                <View style={{ marginTop: 14 }}>
                  <Text style={{ fontSize: 12, fontWeight: "600", color: "#64748B", marginBottom: 6 }}>Suggested queries:</Text>
                  <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
                    {[
                      "Can I eat mango?",
                      "Analyze: 2 bajra roti, dal, dahi",
                      "What should I eat for dinner?",
                      "Mujhe chakkar aa raha hai",
                    ].map((phrase) => (
                      <TouchableOpacity
                        key={phrase}
                        style={{ backgroundColor: "#F1F5F9", paddingHorizontal: 10, paddingVertical: 5, borderRadius: 14, borderWidth: 1, borderColor: "#E2E8F0" }}
                        onPress={() => handleSendAi(phrase)}
                        disabled={isAiLoading}
                      >
                        <Text style={{ fontSize: 12, color: "#334155" }}>{phrase}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>
              </ScrollView>

              {/* Pinned Bottom Input Row */}
              <View style={styles.aiChatBottomBar}>
                <TouchableOpacity
                  style={styles.chatActionIconBtn}
                  onPress={() => setIsAiCameraModalVisible(true)}
                  disabled={isAiLoading}
                  accessibilityRole="button"
                  accessibilityLabel="Take or upload meal photo"
                >
                  <Ionicons name="camera-outline" size={22} color="#0D9488" />
                </TouchableOpacity>

                <TouchableOpacity
                  style={styles.chatActionIconBtn}
                  onPress={() => setIsAiVoiceModalVisible(true)}
                  disabled={isAiLoading}
                  accessibilityRole="button"
                  accessibilityLabel="Record voice message to THALI AI"
                >
                  <Ionicons name="mic-outline" size={22} color="#0D9488" />
                </TouchableOpacity>

                <TextInput
                  style={styles.chatTextInput}
                  placeholder="Ask AI, tap mic, or take photo..."
                  placeholderTextColor="#94A3B8"
                  value={aiQuery}
                  onChangeText={setAiQuery}
                  onSubmitEditing={() => handleSendAi()}
                  editable={!isAiLoading}
                  returnKeyType="send"
                />

                <TouchableOpacity
                  style={[
                    styles.chatSendBtn,
                    aiQuery.trim() && !isAiLoading ? styles.chatSendBtnActive : styles.chatSendBtnDisabled,
                  ]}
                  onPress={() => handleSendAi()}
                  disabled={!aiQuery.trim() || isAiLoading}
                  accessibilityRole="button"
                  accessibilityLabel="Send message to AI"
                >
                  <Ionicons name="arrow-up" size={20} color="#FFFFFF" />
                </TouchableOpacity>
              </View>
            </View>
          ) : (
            <ScrollView
              contentContainerStyle={[
                styles.content,
                {
                  paddingBottom: keyboardHeight > 0 ? keyboardHeight + 30 : Math.max(insets.bottom + 16, spacing.xl),
                },
              ]}
              keyboardShouldPersistTaps="handled"
              keyboardDismissMode="on-drag"
            >
              <View style={styles.disclaimerBox} accessibilityRole="summary">
                <Text style={styles.disclaimerTitle} allowFontScaling>
                  Patient-Safe Care Guide
                </Text>
                <Text style={styles.disclaimerText} allowFontScaling>
                  THALI Assist helps you review and organize your personal recordings. It does not provide medical diagnoses, prescribe treatments, or alter your clinician-authored plan.
                </Text>
              </View>

          {selectedTopic === null ? (
            <View style={styles.promptSection}>
              <Text style={styles.promptHeader} allowFontScaling>
                What would you like help with?
              </Text>

              <TouchableOpacity
                style={[styles.optionCard, { borderColor: "#0D9488", borderWidth: 1.5, backgroundColor: "#F0FDFA" }]}
                onPress={() => handleSelectTopic("ai_chat")}
                activeOpacity={0.7}
                accessibilityRole="button"
                accessibilityLabel="Ask THALI AI Assistant"
              >
                <View style={[styles.optionIconContainer, { backgroundColor: "#0D9488" }]}>
                  <Ionicons name="sparkles" size={20} color="#FFFFFF" />
                </View>
                <View style={styles.optionTextColumn}>
                  <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                    <Text style={[styles.optionTitle, { color: "#0F766E", fontWeight: "700" }]} allowFontScaling>
                      Ask THALI AI
                    </Text>
                    <View style={{ backgroundColor: "#CCFBF1", paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 }}>
                      <Text style={{ fontSize: 10, fontWeight: "700", color: "#0D9488" }}>SARVAM INDIC AI</Text>
                    </View>
                  </View>
                  <Text style={styles.optionSubtitle} allowFontScaling>
                    Ask diet questions, analyze Indian meals with ICMR tables, or check symptoms in Hinglish.
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color="#0D9488" />
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.optionCard}
                onPress={() => handleSelectTopic("voice")}
                activeOpacity={0.7}
                accessibilityRole="button"
                accessibilityLabel="Voice / Spoken Log Draft"
              >
                <View style={[styles.optionIconContainer, { backgroundColor: "rgba(13, 148, 136, 0.12)" }]}>
                  <Ionicons name="mic-outline" size={22} color={colors.primary} />
                </View>
                <View style={styles.optionTextColumn}>
                  <Text style={styles.optionTitle} allowFontScaling>
                    Voice / Spoken Log Draft
                  </Text>
                  <Text style={styles.optionSubtitle} allowFontScaling>
                    Speak or type a meal or glucose log. Review draft before saving.
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.optionCard}
                onPress={() => handleSelectTopic("today")}
                activeOpacity={0.7}
                accessibilityRole="button"
                accessibilityLabel="Understand today's records"
              >
                <View style={[styles.optionIconContainer, { backgroundColor: "rgba(59, 130, 246, 0.12)" }]}>
                  <Ionicons name="stats-chart-outline" size={20} color="#2563EB" />
                </View>
                <View style={styles.optionTextColumn}>
                  <Text style={styles.optionTitle} allowFontScaling>
                    {"Understand today's records"}
                  </Text>
                  <Text style={styles.optionSubtitle} allowFontScaling>
                    Review glucose patterns and meals you logged today.
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.optionCard}
                onPress={() => handleSelectTopic("summarize_week")}
                activeOpacity={0.7}
                accessibilityRole="button"
                accessibilityLabel="Summarize My Week"
              >
                <View style={[styles.optionIconContainer, { backgroundColor: "rgba(13, 92, 117, 0.12)" }]}>
                  <Ionicons name="bar-chart-outline" size={20} color={colors.primary} />
                </View>
                <View style={styles.optionTextColumn}>
                  <Text style={styles.optionTitle} allowFontScaling>
                    Summarize My Week
                  </Text>
                  <Text style={styles.optionSubtitle} allowFontScaling>
                    Deterministic 7-day patient summary, coverage, and timeline patterns.
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.optionCard}
                onPress={() => handleSelectTopic("meal")}
                activeOpacity={0.7}
                accessibilityRole="button"
                accessibilityLabel="Understand a meal entry"
              >
                <View style={[styles.optionIconContainer, { backgroundColor: "rgba(245, 158, 11, 0.12)" }]}>
                  <Ionicons name="restaurant-outline" size={20} color="#D97706" />
                </View>
                <View style={styles.optionTextColumn}>
                  <Text style={styles.optionTitle} allowFontScaling>
                    Understand a meal entry
                  </Text>
                  <Text style={styles.optionSubtitle} allowFontScaling>
                    How your meal portions connect to your care plan.
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.optionCard}
                onPress={() => handleSelectTopic("appointment")}
                activeOpacity={0.7}
                accessibilityRole="button"
                accessibilityLabel="Prepare for an appointment"
              >
                <View style={[styles.optionIconContainer, { backgroundColor: "rgba(16, 185, 129, 0.12)" }]}>
                  <Ionicons name="calendar-outline" size={20} color="#059669" />
                </View>
                <View style={styles.optionTextColumn}>
                  <Text style={styles.optionTitle} allowFontScaling>
                    Prepare for an appointment
                  </Text>
                  <Text style={styles.optionSubtitle} allowFontScaling>
                    Checklist of summaries and questions for your doctor.
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
              </TouchableOpacity>
            </View>
          ) : null}

          {selectedTopic === "voice" ? (
            <View style={styles.topicDetail}>
              <View style={styles.provenanceTag}>
                <Text style={styles.provenanceText} allowFontScaling>
                  VOICE CAPTURE ASSISTANT
                </Text>
              </View>
              <Text style={styles.topicTitle} allowFontScaling>
                Spoken & Dictation Draft
              </Text>
              <Text style={styles.topicBody} allowFontScaling>
                Dictate or type what you ate or your glucose reading. A structured draft will be prepared for your explicit confirmation before anything is saved.
              </Text>

              {voiceSaveSuccess ? (
                <View style={styles.voiceSuccessBanner}>
                  <View style={{ flexDirection: "row", alignItems: "center", marginBottom: 4 }}>
                    <Ionicons name="checkmark-circle" size={16} color="#065F46" style={{ marginRight: 6 }} />
                    <Text style={styles.voiceSuccessText} allowFontScaling>
                      {voiceSaveSuccess}
                    </Text>
                  </View>
                  <TouchableOpacity
                    style={styles.viewRecordsBtn}
                    onPress={() => {
                      onClose();
                      onNavigateToRecords?.();
                    }}
                    accessibilityRole="button"
                    accessibilityLabel="View in timeline"
                  >
                    <Text style={styles.viewRecordsBtnText} allowFontScaling>
                      Open Timeline History
                    </Text>
                  </TouchableOpacity>
                </View>
              ) : null}

              {voiceError ? (
                <View style={styles.voiceErrorBanner}>
                  <Ionicons name="alert-circle" size={16} color="#991B1B" style={{ marginRight: 6 }} />
                  <Text style={styles.voiceErrorText} allowFontScaling>
                    {voiceError}
                  </Text>
                </View>
              ) : null}

              <View style={styles.voiceInputCard}>
                <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.xs }}>
                  <Text style={styles.inputLabel} allowFontScaling>
                    Dictate or type your entry:
                  </Text>
                  <TouchableOpacity
                    style={styles.voiceMicInlineBtn}
                    onPress={() => setIsDirectVoiceModalVisible(true)}
                    accessibilityRole="button"
                    accessibilityLabel="Record voice"
                  >
                    <Ionicons name="mic" size={14} color="#0D9488" style={{ marginRight: 4 }} />
                    <Text style={styles.voiceMicInlineBtnText}>Record Voice</Text>
                  </TouchableOpacity>
                </View>
                <TextInput
                  style={styles.voiceTextInput}
                  placeholder="e.g. Fasting sugar 114 mg/dL or 2 rotis with dal for lunch"
                  placeholderTextColor={colors.textSecondary}
                  value={voiceInput}
                  onChangeText={setVoiceInput}
                  multiline
                  accessibilityLabel="Voice phrase text input"
                />

                <Text style={styles.quickSamplesLabel} allowFontScaling>
                  Or choose a quick phrase:
                </Text>
                <View style={styles.quickSamplesRow}>
                  {[
                    "Fasting sugar 114",
                    "Post-lunch glucose 156",
                    "2 rotis with dal for lunch",
                    "Afternoon tea and roasted chana",
                  ].map((phrase) => (
                    <TouchableOpacity
                      key={phrase}
                      style={styles.sampleChip}
                      onPress={() => {
                        setVoiceInput(phrase);
                        handleParseVoiceInput(phrase);
                      }}
                      accessibilityRole="button"
                    >
                      <Text style={styles.sampleChipText} allowFontScaling>
                        {phrase}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>

                <TouchableOpacity
                  style={[
                    styles.parseBtn,
                    !voiceInput.trim() && styles.parseBtnDisabled,
                  ]}
                  onPress={() => handleParseVoiceInput(voiceInput)}
                  disabled={!voiceInput.trim()}
                  accessibilityRole="button"
                  accessibilityLabel="Generate structured draft"
                >
                  <Text style={styles.parseBtnText} allowFontScaling>
                    Generate Structured Draft
                  </Text>
                </TouchableOpacity>
              </View>

              {voiceDraft ? (
                <View style={styles.draftCard}>
                  <View style={styles.draftHeaderRow}>
                    <View style={styles.draftBadge}>
                      <Text style={styles.draftBadgeText} allowFontScaling>
                        UNCONFIRMED DRAFT
                      </Text>
                    </View>
                    <Text style={styles.draftTypeLabel} allowFontScaling>
                      {voiceDraft.kind === "glucose" ? "Glucose Observation" : "Meal Observation"}
                    </Text>
                  </View>

                  <View style={styles.draftFieldRow}>
                    <Text style={styles.draftFieldLabel} allowFontScaling>
                      {voiceDraft.kind === "glucose" ? "Blood Glucose:" : "Meal Description:"}
                    </Text>
                    <Text style={styles.draftFieldValue} allowFontScaling>
                      {voiceDraft.kind === "glucose" ? `${voiceDraft.value} mg/dL` : voiceDraft.description}
                    </Text>
                  </View>

                  <View style={styles.draftFieldRow}>
                    <Text style={styles.draftFieldLabel} allowFontScaling>
                      {voiceDraft.kind === "glucose" ? "Context / Tag:" : "Meal Type:"}
                    </Text>
                    <Text style={styles.draftFieldValue} allowFontScaling>
                      {voiceDraft.kind === "glucose"
                        ? voiceDraft.tag ? voiceDraft.tag.toUpperCase() : "Unspecified (Tap below)"
                        : voiceDraft.mealType ? voiceDraft.mealType.toUpperCase() : "Unspecified (Tap below)"}
                    </Text>
                  </View>

                  {voiceDraft.kind === "glucose" && voiceDraft.missingTag ? (
                    <View style={styles.clarificationBox}>
                      <Text style={styles.clarificationPrompt} allowFontScaling>
                        Clarification: When was this reading taken?
                      </Text>
                      <View style={styles.clarificationOptionsRow}>
                        {(
                          [
                            { id: "fasting", label: "Fasting" },
                            { id: "premeal", label: "Pre-meal" },
                            { id: "postbreakfast", label: "Post-breakfast" },
                            { id: "postlunch", label: "Post-lunch" },
                            { id: "postdinner", label: "Post-dinner" },
                          ] as const
                        ).map((opt) => (
                          <TouchableOpacity
                            key={opt.id}
                            style={[
                              styles.clarificationChip,
                              voiceDraft.tag === opt.id && styles.clarificationChipActive,
                            ]}
                            onPress={() =>
                              setVoiceDraft({
                                ...voiceDraft,
                                tag: opt.id,
                                missingTag: false,
                              })
                            }
                            accessibilityRole="button"
                          >
                            <Text
                              style={[
                                styles.clarificationChipText,
                                voiceDraft.tag === opt.id && styles.clarificationChipTextActive,
                              ]}
                              allowFontScaling
                            >
                              {opt.label}
                            </Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </View>
                  ) : null}

                  {voiceDraft.kind === "meal" && voiceDraft.missingMealType ? (
                    <View style={styles.clarificationBox}>
                      <Text style={styles.clarificationPrompt} allowFontScaling>
                        Clarification: Which meal was this?
                      </Text>
                      <View style={styles.clarificationOptionsRow}>
                        {(
                          [
                            { id: "breakfast", label: "Breakfast" },
                            { id: "lunch", label: "Lunch" },
                            { id: "dinner", label: "Dinner" },
                            { id: "snack", label: "Snack" },
                          ] as const
                        ).map((opt) => (
                          <TouchableOpacity
                            key={opt.id}
                            style={[
                              styles.clarificationChip,
                              voiceDraft.mealType === opt.id && styles.clarificationChipActive,
                            ]}
                            onPress={() =>
                              setVoiceDraft({
                                ...voiceDraft,
                                mealType: opt.id,
                                missingMealType: false,
                              })
                            }
                            accessibilityRole="button"
                          >
                            <Text
                              style={[
                                styles.clarificationChipText,
                                voiceDraft.mealType === opt.id && styles.clarificationChipTextActive,
                              ]}
                              allowFontScaling
                            >
                              {opt.label}
                            </Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </View>
                  ) : null}

                  <TouchableOpacity
                    style={[
                      styles.confirmSaveBtn,
                      isSaving && styles.confirmSaveBtnBusy,
                    ]}
                    onPress={handleConfirmAndSave}
                    disabled={isSaving}
                    accessibilityRole="button"
                    accessibilityLabel="Confirm and save draft to health record"
                  >
                    {isSaving ? (
                      <ActivityIndicator color={colors.textOnPrimary} size="small" />
                    ) : (
                      <Text style={styles.confirmSaveBtnText} allowFontScaling>
                        ✓ Confirm & Save to Record
                      </Text>
                    )}
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={styles.discardBtn}
                    onPress={() => setVoiceDraft(null)}
                    accessibilityRole="button"
                    accessibilityLabel="Discard draft"
                  >
                    <Text style={styles.discardBtnText} allowFontScaling>
                      Discard Draft
                    </Text>
                  </TouchableOpacity>
                </View>
              ) : null}

              <TouchableOpacity
                style={styles.backLink}
                onPress={() => setSelectedTopic(null)}
                accessibilityRole="button"
                accessibilityLabel="Choose another question"
              >
                <Ionicons name="arrow-back" size={14} color={colors.primary} style={{ marginRight: 6 }} />
                <Text style={styles.backLinkText} allowFontScaling>
                  Choose another topic
                </Text>
              </TouchableOpacity>
            </View>
          ) : null}

          {selectedTopic === "today" ? (
            <View style={styles.topicDetail}>
              <View style={styles.provenanceTag}>
                <Text style={styles.provenanceText} allowFontScaling>
                  PATIENT DATA REVIEW
                </Text>
              </View>
              <Text style={styles.topicTitle} allowFontScaling>
                {"Today's Care Insights"}
              </Text>
              <Text style={styles.topicBody} allowFontScaling>
                • Your recorded glucose readings are saved and available for clinician review.
                {"\n\n"}
                • Regular logging around meals helps your care team understand how different foods influence your day.
                {"\n\n"}
                • All readings are cryptographically stored and synchronized with your clinical facility.
              </Text>

              <TouchableOpacity
                style={styles.actionButton}
                onPress={() => {
                  onClose();
                  onNavigateToRecords?.();
                }}
                accessibilityRole="button"
                accessibilityLabel="View full timeline records"
              >
                <Text style={styles.actionButtonText} allowFontScaling>
                  Open Timeline History
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.backLink}
                onPress={() => setSelectedTopic(null)}
                accessibilityRole="button"
                accessibilityLabel="Choose another question"
              >
                <Ionicons name="arrow-back" size={14} color={colors.primary} style={{ marginRight: 6 }} />
                <Text style={styles.backLinkText} allowFontScaling>
                  Choose another topic
                </Text>
              </TouchableOpacity>
            </View>
          ) : null}

          {selectedTopic === "meal" ? (
            <View style={styles.topicDetail}>
              <View style={styles.provenanceTag}>
                <Text style={styles.provenanceText} allowFontScaling>
                  NUTRITION GUIDANCE
                </Text>
              </View>
              <Text style={styles.topicTitle} allowFontScaling>
                Understanding Meal Portions
              </Text>
              <Text style={styles.topicBody} allowFontScaling>
                • THALI uses standard Katori measures (Small 100ml, Medium 150ml, Large 200ml) to help keep portion logging consistent.
                {"\n\n"}
                • Consistent portions allow your dietitian and doctor to evaluate your nutritional balance accurately without confusing calculations.
              </Text>

              <TouchableOpacity
                style={styles.actionButton}
                onPress={() => {
                  onClose();
                  onNavigateToMeal?.();
                }}
                accessibilityRole="button"
                accessibilityLabel="Log a new meal"
              >
                <Text style={styles.actionButtonText} allowFontScaling>
                  Log a Meal
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.backLink}
                onPress={() => setSelectedTopic(null)}
                accessibilityRole="button"
                accessibilityLabel="Choose another question"
              >
                <Ionicons name="arrow-back" size={14} color={colors.primary} style={{ marginRight: 6 }} />
                <Text style={styles.backLinkText} allowFontScaling>
                  Choose another topic
                </Text>
              </TouchableOpacity>
            </View>
          ) : null}

          {selectedTopic === "appointment" ? (
            <View style={styles.topicDetail}>
              <View style={styles.provenanceTag}>
                <Text style={styles.provenanceText} allowFontScaling>
                  CLINIC PREPARATION
                </Text>
              </View>
              <Text style={styles.topicTitle} allowFontScaling>
                Preparing for Your Next Visit
              </Text>
              <Text style={styles.topicBody} allowFontScaling>
                • Ensure your latest glucose observations and medication marks are logged up to today.
                {"\n\n"}
                • In the &apos;You&apos; tab, you can view your verified Clinical Care Summaries (PDF).
                {"\n\n"}
                • Note any symptoms or side-effects to share directly with your clinician.
              </Text>

              <TouchableOpacity
                style={styles.backLink}
                onPress={() => setSelectedTopic(null)}
                accessibilityRole="button"
                accessibilityLabel="Choose another question"
              >
                <Ionicons name="arrow-back" size={14} color={colors.primary} style={{ marginRight: 6 }} />
                <Text style={styles.backLinkText} allowFontScaling>
                  Choose another topic
                </Text>
              </TouchableOpacity>
            </View>
          ) : null}

          {selectedTopic === "summarize_week" ? (
            <View style={styles.topicDetail}>
              <View style={[styles.provenanceTag, { backgroundColor: colors.tileAqua }]}>
                <Text style={[styles.provenanceText, { color: colors.primary }]} allowFontScaling>
                  DETERMINISTIC 7-DAY PATIENT HEALTH SUMMARY
                </Text>
              </View>
              <Text style={styles.topicTitle} allowFontScaling>
                Weekly Health Summary
              </Text>
              <Text style={styles.topicBody} allowFontScaling>
                • ADA/EASD Glycemic Metrics: Calculations evaluate Time-in-Range (70–180 mg/dL), Mean glucose, and variability over a rolling 7-day window.
                {"\n\n"}
                • Temporal Associations: Meals and physical activities are aligned with adjacent glucose readings to observe non-causal contextual relationships.
                {"\n\n"}
                • Auditable Evidence: Every insight is backed by exact timestamped observations that you confirmed.
                {"\n\n"}
                • Clinician Shared Review: This summary helps prepare discussion topics for your treating doctor without autonomous AI diagnoses.
              </Text>

              <TouchableOpacity
                style={[styles.actionButton, { flexDirection: "row" }]}
                onPress={() => {
                  onClose();
                  onNavigateToReports?.();
                }}
                accessibilityRole="button"
                accessibilityLabel="Open Weekly Health Summary"
              >
                <Text style={styles.actionButtonText} allowFontScaling>
                  View Weekly Health Summary
                </Text>
                <Ionicons name="arrow-forward" size={16} color="#FFFFFF" style={{ marginLeft: 6 }} />
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.backLink}
                onPress={() => setSelectedTopic(null)}
                accessibilityRole="button"
                accessibilityLabel="Choose another question"
              >
                <Ionicons name="arrow-back" size={14} color={colors.primary} style={{ marginRight: 6 }} />
                <Text style={styles.backLinkText} allowFontScaling>
                  Choose another topic
                </Text>
              </TouchableOpacity>
            </View>
          ) : null}
            </ScrollView>
          )}

        {/* Voice Record Modal for THALI AI */}
        <VoiceRecordModal
          visible={isAiVoiceModalVisible}
          onClose={() => setIsAiVoiceModalVisible(false)}
          title="Speak to THALI AI"
          subtitle="Dictate your food, glucose reading, or symptom question in English or Hinglish."
          placeholderHint="e.g. 'Maine 2 bajra roti aur dal khayi' or 'What can I eat for evening snack?'"
          onTranscribeSuccess={(transcript) => {
            setIsAiVoiceModalVisible(false);
            if (transcript.trim()) {
              handleSendAi(transcript.trim());
            }
          }}
          testID="thali-ai-voice-modal"
        />

        {/* Camera / Meal Photo Modal for THALI AI */}
        <MealPhotoModal
          visible={isAiCameraModalVisible}
          onClose={() => setIsAiCameraModalVisible(false)}
          patientName={patientName}
          onPhotoAnalyzed={(result, photoUri) => {
            setIsAiCameraModalVisible(false);
            handleReceivePhotoAnalysis(result, photoUri);
          }}
          onDirectLog={async (result, photoUri) => {
            setIsAiCameraModalVisible(false);
            handleReceivePhotoAnalysis(result, photoUri);
            try {
              await logMeal.mutateAsync({ description: result.description || "Meal photo" });
              setVoiceSaveSuccess(`Saved meal: "${result.description}"`);
            } catch (e: any) {
              setVoiceError("Failed to save meal to log.");
            }
          }}
          testID="thali-ai-camera-modal"
        />

        {/* Direct Voice Record Modal for Voice Topic */}
        <VoiceRecordModal
          visible={isDirectVoiceModalVisible}
          onClose={() => setIsDirectVoiceModalVisible(false)}
          title="Voice Capture"
          subtitle="Speak your glucose reading or meal description."
          placeholderHint="e.g. 'Fasting sugar 114' or '2 rotis with dal for lunch'"
          onTranscribeSuccess={(transcript) => {
            setIsDirectVoiceModalVisible(false);
            if (transcript.trim()) {
              setVoiceInput(transcript.trim());
              handleParseVoiceInput(transcript.trim());
            }
          }}
          testID="thali-direct-voice-modal"
        />
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.surface,
  },
  headerTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  headerIconBadge: {
    width: 38,
    height: 38,
    borderRadius: 12,
    backgroundColor: "#F0FDFA",
    borderWidth: 1,
    borderColor: "rgba(13, 148, 136, 0.15)",
    alignItems: "center",
    justifyContent: "center",
  },
  title: {
    fontSize: 18,
    fontWeight: "800",
    color: "#0F172A",
    letterSpacing: -0.2,
  },
  subtitle: {
    fontSize: 12,
    color: "#64748B",
    fontWeight: "500",
  },
  closeButton: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  content: {
    padding: spacing.md,
  },
  offlineNotice: {
    backgroundColor: colors.warning,
    flexDirection: "row",
    alignItems: "center",
    padding: spacing.sm,
    gap: spacing.xs,
  },
  offlineIcon: {
    fontSize: 16,
  },
  offlineText: {
    color: colors.textOnPrimary,
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.medium,
    flex: 1,
  },
  disclaimerBox: {
    backgroundColor: "#F0F7F9",
    borderRadius: radii.md,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  disclaimerTitle: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
    color: colors.primary,
    marginBottom: 2,
    letterSpacing: 0.5,
  },
  disclaimerText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  promptSection: {
    gap: spacing.sm,
  },
  promptHeader: {
    fontSize: typography.fontSize.body,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  optionCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  optionIconContainer: {
    width: 36,
    height: 36,
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
  },
  optionIcon: {
    fontSize: 22,
  },
  optionTextColumn: {
    flex: 1,
  },
  optionTitle: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  optionSubtitle: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  chevron: {
    fontSize: 18,
    color: colors.textSecondary,
  },
  topicDetail: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    gap: spacing.md,
  },
  provenanceTag: {
    alignSelf: "flex-start",
    backgroundColor: "#E8F4F8",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radii.sm,
  },
  provenanceText: {
    fontSize: 10,
    fontWeight: typography.weight.bold,
    color: colors.primary,
    letterSpacing: 0.8,
  },
  topicTitle: {
    fontSize: typography.fontSize.headline,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  topicBody: {
    fontSize: typography.fontSize.body,
    color: colors.textPrimary,
    lineHeight: typography.lineHeight.body,
  },
  actionButton: {
    backgroundColor: colors.primary,
    borderRadius: radii.pill,
    minHeight: 46,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
    shadowRadius: 4,
    elevation: 2,
    marginTop: spacing.sm,
  },
  actionButtonText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "700",
  },
  backLink: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    minHeight: 44,
    marginTop: spacing.xs,
  },
  backLinkText: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: "600",
  },
  voiceSuccessBanner: {
    backgroundColor: colors.tileGreen,
    padding: spacing.md,
    borderRadius: radii.md,
    marginBottom: spacing.md,
  },
  voiceSuccessText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.leafGreen,
    fontWeight: typography.weight.semibold,
  },
  viewRecordsBtn: {
    marginTop: spacing.xs,
    alignSelf: "flex-start",
  },
  viewRecordsBtnText: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
    color: colors.leafGreen,
    textDecorationLine: "underline",
  },
  voiceErrorBanner: {
    backgroundColor: colors.tilePink,
    padding: spacing.md,
    borderRadius: radii.md,
    marginBottom: spacing.md,
  },
  voiceErrorText: {
    fontSize: typography.fontSize.bodySmall,
    color: colors.critical,
    fontWeight: typography.weight.medium,
  },
  voiceInputCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.md,
  },
  inputLabel: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.semibold,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  voiceTextInput: {
    backgroundColor: colors.backgroundRaised,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.sm,
    fontSize: typography.fontSize.bodySmall,
    color: colors.textPrimary,
    minHeight: 56,
  },
  quickSamplesLabel: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    marginTop: spacing.sm,
    marginBottom: 4,
  },
  quickSamplesRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
    marginBottom: spacing.md,
  },
  sampleChip: {
    backgroundColor: colors.backgroundRaised,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: colors.border,
  },
  sampleChipText: {
    fontSize: 11,
    color: colors.textPrimary,
  },
  parseBtn: {
    backgroundColor: colors.primary,
    borderRadius: radii.pill,
    minHeight: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
  },
  parseBtnDisabled: {
    opacity: 0.5,
  },
  parseBtnText: {
    color: colors.textOnPrimary,
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.semibold,
  },
  draftCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    padding: spacing.md,
    borderWidth: 2,
    borderColor: colors.assistive,
    marginBottom: spacing.md,
  },
  draftHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  draftBadge: {
    backgroundColor: colors.tileYellow,
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
    borderRadius: radii.sm,
  },
  draftBadgeText: {
    fontSize: 10,
    fontWeight: typography.weight.bold,
    color: colors.assistive,
  },
  draftTypeLabel: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  draftFieldRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 4,
    borderBottomWidth: 1,
    borderBottomColor: colors.backgroundRaised,
  },
  draftFieldLabel: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
  },
  draftFieldValue: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.bold,
    color: colors.textPrimary,
  },
  clarificationBox: {
    backgroundColor: colors.backgroundRaised,
    padding: spacing.sm,
    borderRadius: radii.md,
    marginTop: spacing.sm,
    marginBottom: spacing.sm,
  },
  clarificationPrompt: {
    fontSize: typography.fontSize.caption,
    fontWeight: typography.weight.semibold,
    color: colors.assistive,
    marginBottom: spacing.xs,
  },
  clarificationOptionsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  clarificationChip: {
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
  },
  clarificationChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  clarificationChipText: {
    fontSize: typography.fontSize.caption,
    color: colors.textPrimary,
  },
  clarificationChipTextActive: {
    color: colors.textOnPrimary,
    fontWeight: typography.weight.bold,
  },
  confirmSaveBtn: {
    backgroundColor: colors.primary,
    borderRadius: radii.pill,
    minHeight: touchTarget.min,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.md,
  },
  confirmSaveBtnBusy: {
    opacity: 0.7,
  },
  confirmSaveBtnText: {
    color: colors.textOnPrimary,
    fontSize: typography.fontSize.bodySmall,
    fontWeight: typography.weight.bold,
  },
  discardBtn: {
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.xs,
    paddingVertical: spacing.xs,
  },
  discardBtnText: {
    color: colors.textSecondary,
    fontSize: typography.fontSize.caption,
  },
  keyboardAvoidContainer: {
    flex: 1,
  },
  aiChatScreen: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: "space-between",
  },
  aiMessagesScrollView: {
    flex: 1,
  },
  aiMessagesContent: {
    padding: spacing.md,
    paddingBottom: spacing.lg,
  },
  aiChatBottomBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: -2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 4,
  },
  chatActionIconBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: "#F0FDFA",
    borderWidth: 1,
    borderColor: "rgba(13, 148, 136, 0.25)",
    alignItems: "center",
    justifyContent: "center",
  },
  chatTextInput: {
    flex: 1,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#CBD5E1",
    borderRadius: 21,
    paddingHorizontal: 14,
    paddingVertical: Platform.OS === "ios" ? 10 : 8,
    fontSize: 14,
    color: colors.textPrimary,
    minHeight: 42,
    maxHeight: 100,
  },
  chatSendBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    alignItems: "center",
    justifyContent: "center",
  },
  chatSendBtnActive: {
    backgroundColor: "#0D9488",
  },
  chatSendBtnDisabled: {
    backgroundColor: "#94A3B8",
  },
  chatImageContainer: {
    marginBottom: 8,
    borderRadius: 10,
    overflow: "hidden",
    backgroundColor: "#E2E8F0",
  },
  chatThumbnail: {
    width: 220,
    height: 160,
    borderRadius: 10,
  },
  headerBackBtn: {
    width: 38,
    height: 38,
    borderRadius: 12,
    backgroundColor: "#F0FDFA",
    borderWidth: 1,
    borderColor: "rgba(13, 148, 136, 0.15)",
    alignItems: "center",
    justifyContent: "center",
  },
  voiceMicInlineBtn: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#F0FDFA",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "rgba(13, 148, 136, 0.3)",
  },
  voiceMicInlineBtnText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#0D9488",
  },
});
