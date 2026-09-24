import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  AppState,
  Image,
  Linking,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  type AppStateStatus,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Camera, CameraView, useCameraPermissions } from "expo-camera";
import { colors, radii, spacing, typography } from "../../theming/tokens";
import {
  pickMealPhotoFromLibrary,
  analyzeMealPhoto,
  convertUriToBase64,
  hasNativeImagePicker,
  type CapturedPhotoResult,
} from "../../services/camera/mealPhotoService";
import type { AnalyzeMealPhotoAiResponse } from "../../services/schemas/ai";

export type MealPhotoModalProps = {
  visible: boolean;
  onClose: () => void;
  patientName?: string;
  onPhotoAnalyzed: (result: AnalyzeMealPhotoAiResponse, photoUri: string) => void;
  onDirectLog?: (result: AnalyzeMealPhotoAiResponse, photoUri: string) => Promise<void>;
  testID?: string;
};

export function MealPhotoModal({
  visible,
  onClose,
  patientName = "",
  onPhotoAnalyzed,
  onDirectLog,
  testID,
}: MealPhotoModalProps) {
  const [photo, setPhoto] = useState<CapturedPhotoResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isLogging, setIsLogging] = useState(false);
  const [isCapturing, setIsCapturing] = useState(false);
  const [facing, setFacing] = useState<"back" | "front">("back");
  const [analysis, setAnalysis] = useState<AnalyzeMealPhotoAiResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const cameraRef = useRef<any>(null);
  const [cameraPermission, requestCameraPermission, getCameraPermission] = useCameraPermissions();
  const [isRequestingPermission, setIsRequestingPermission] = useState(false);

  // Auto-refresh camera permission when modal becomes visible or when returning from iOS Settings
  useEffect(() => {
    if (!visible) return;

    void getCameraPermission();

    const handleAppStateChange = (nextAppState: AppStateStatus) => {
      if (nextAppState === "active") {
        void getCameraPermission();
      }
    };

    const sub = AppState.addEventListener("change", handleAppStateChange);
    return () => {
      sub.remove();
    };
  }, [visible, getCameraPermission]);

  const handleOpenSettings = async () => {
    try {
      await Linking.openSettings();
    } catch {
      Alert.alert(
        "Open Settings",
        "Please open your device Settings, find THALI x P.L.A.T.E, and enable Camera access."
      );
    }
  };

  const handleRequestCameraAccess = async () => {
    try {
      setIsRequestingPermission(true);
      setError(null);

      // If OS already denied or cannot ask again, direct immediately to Settings
      if (
        cameraPermission &&
        (!cameraPermission.canAskAgain || cameraPermission.status === "denied")
      ) {
        Alert.alert(
          "Camera Access Required",
          "Camera permission is currently turned off for THALI in device settings. Please allow Camera access to scan meals.",
          [
            { text: "Cancel", style: "cancel" },
            {
              text: "Open Settings",
              onPress: () => {
                void handleOpenSettings();
              },
            },
          ]
        );
        return;
      }

      const result = await requestCameraPermission();

      if (!result?.granted) {
        if (!result?.canAskAgain || result?.status === "denied") {
          Alert.alert(
            "Camera Access Required",
            "Camera permission is required to photograph your meal. Please enable Camera in your device Settings.",
            [
              { text: "Cancel", style: "cancel" },
              {
                text: "Open Settings",
                onPress: () => {
                  void handleOpenSettings();
                },
              },
            ]
          );
        } else {
          setError("Camera permission was not granted. Please allow camera access to scan your meal.");
        }
      }
    } catch (err: any) {
      console.warn("Camera permission request failed:", err);
      Alert.alert(
        "Camera Permission",
        "Could not request camera access directly. Would you like to open Settings?",
        [
          { text: "Cancel", style: "cancel" },
          {
            text: "Open Settings",
            onPress: () => {
              void handleOpenSettings();
            },
          },
        ]
      );
    } finally {
      setIsRequestingPermission(false);
    }
  };

  const reset = () => {
    setPhoto(null);
    setAnalysis(null);
    setIsAnalyzing(false);
    setIsLogging(false);
    setIsCapturing(false);
    setError(null);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const processCapturedPhoto = async (captured: CapturedPhotoResult | null) => {
    if (!captured) return;
    setPhoto(captured);
    setError(null);
    setIsAnalyzing(true);

    try {
      const res = await analyzeMealPhoto(captured, patientName);
      setAnalysis(res);
    } catch (err: any) {
      setError(
        err?.message ||
          "Failed to analyze meal photo with AI. Please check your connection or try again."
      );
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleCapturePhoto = async () => {
    if (!cameraRef.current || isCapturing) return;
    try {
      setIsCapturing(true);
      setError(null);
      const pic = await cameraRef.current.takePictureAsync({
        quality: 0.8,
        base64: true,
      });

      if (!pic?.uri) {
        throw new Error("Could not capture image from camera.");
      }

      let base64 = pic.base64 || "";
      if (!base64) {
        base64 = await convertUriToBase64(pic.uri);
      }

      const captured: CapturedPhotoResult = {
        uri: pic.uri,
        base64,
        mimeType: pic.uri.toLowerCase().endsWith(".png") ? "image/png" : "image/jpeg",
        width: pic.width,
        height: pic.height,
      };

      await processCapturedPhoto(captured);
    } catch (err: any) {
      setError(err?.message || "Failed to capture photo.");
    } finally {
      setIsCapturing(false);
    }
  };

  const handlePickPhoto = async () => {
    try {
      setError(null);
      if (!hasNativeImagePicker()) {
        setError(
          "Gallery upload requires rebuilding the app binary with the new module (npx expo run:ios). Please use the live camera to snap your meal!"
        );
        return;
      }
      const captured = await pickMealPhotoFromLibrary();
      if (captured) {
        await processCapturedPhoto(captured);
      }
    } catch (err: any) {
      setError(err?.message || "Could not access photo library.");
    }
  };

  const handleApplyDescription = () => {
    if (analysis && photo) {
      onPhotoAnalyzed(analysis, photo.uri);
      handleClose();
    }
  };

  const handleDirectLog = async () => {
    if (!analysis || !photo || !onDirectLog) return;
    try {
      setIsLogging(true);
      await onDirectLog(analysis, photo.uri);
      handleClose();
    } catch (err: any) {
      setError(err?.message || "Failed to log meal observation.");
    } finally {
      setIsLogging(false);
    }
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={handleClose}
      testID={testID}
    >
      <View style={styles.overlay}>
        <View style={styles.modalCard}>
          {/* Header */}
          <View style={styles.headerRow}>
            <View style={styles.headerTitles}>
              <Text style={styles.title} allowFontScaling numberOfLines={1}>
                Meal Photo Scanner
              </Text>
              <Text style={styles.subtitle} allowFontScaling>
                Gemini Vision AI Nutritional Analysis
              </Text>
            </View>
            <TouchableOpacity
              onPress={handleClose}
              style={styles.closeButton}
              accessibilityRole="button"
              accessibilityLabel="Close camera scanner"
            >
              <Ionicons name="close" size={20} color="#64748B" />
            </TouchableOpacity>
          </View>

          {/* Error Message */}
          {error ? (
            <View style={styles.errorBanner}>
              <Ionicons
                name="alert-circle-outline"
                size={18}
                color="#DC2626"
                style={{ marginRight: 6 }}
              />
              <Text style={styles.errorText} allowFontScaling>
                {error}
              </Text>
            </View>
          ) : null}

          <ScrollView
            style={styles.scrollArea}
            contentContainerStyle={styles.scrollContent}
            showsVerticalScrollIndicator={false}
          >
            {/* State 1: Live Camera Viewfinder (when no photo taken yet) */}
            {!photo ? (
              cameraPermission === null ? (
                <View style={styles.permissionCard}>
                  <ActivityIndicator size="large" color="#0D9488" />
                  <Text style={styles.permissionSubtitle} allowFontScaling>
                    Checking camera access…
                  </Text>
                </View>
              ) : !cameraPermission.granted ? (
                <View style={styles.permissionCard}>
                  <View style={styles.permissionIconCircle}>
                    <Ionicons name="camera-outline" size={36} color="#0D9488" />
                  </View>
                  <Text style={styles.permissionTitle} allowFontScaling>
                    Camera Access Required
                  </Text>
                  <Text style={styles.permissionSubtitle} allowFontScaling>
                    {!cameraPermission.canAskAgain || cameraPermission.status === "denied"
                      ? "Camera access is currently turned off in your device settings. Tap below to open Settings and turn Camera ON."
                      : "THALI P.L.A.T.E needs access to your camera to photograph your meal and analyze nutritional content with Gemini AI."}
                  </Text>

                  <TouchableOpacity
                    style={[
                      styles.permissionButton,
                      (!cameraPermission.canAskAgain || cameraPermission.status === "denied") &&
                        styles.permissionButtonSettings,
                    ]}
                    onPress={
                      !cameraPermission.canAskAgain || cameraPermission.status === "denied"
                        ? handleOpenSettings
                        : handleRequestCameraAccess
                    }
                    disabled={isRequestingPermission}
                    accessibilityRole="button"
                    accessibilityLabel={
                      !cameraPermission.canAskAgain || cameraPermission.status === "denied"
                        ? "Open Device Settings"
                        : "Allow Camera Access"
                    }
                    activeOpacity={0.8}
                  >
                    {isRequestingPermission ? (
                      <ActivityIndicator size="small" color="#FFFFFF" />
                    ) : (
                      <>
                        <Ionicons
                          name={
                            !cameraPermission.canAskAgain || cameraPermission.status === "denied"
                              ? "settings-outline"
                              : "checkmark-circle-outline"
                          }
                          size={20}
                          color="#FFFFFF"
                          style={{ marginRight: 8 }}
                        />
                        <Text style={styles.permissionButtonText} allowFontScaling>
                          {!cameraPermission.canAskAgain || cameraPermission.status === "denied"
                            ? "Open Device Settings"
                            : "Allow Camera Access"}
                        </Text>
                      </>
                    )}
                  </TouchableOpacity>

                  {!cameraPermission.canAskAgain || cameraPermission.status === "denied" ? (
                    <Text style={styles.settingsHintText} allowFontScaling>
                      1. Tap "Open Device Settings" above{"\n"}
                      2. Toggle Camera to ON{"\n"}
                      3. Return here to take meal photos
                    </Text>
                  ) : null}

                  {/* Secondary Alternative: Upload from Gallery */}
                  <TouchableOpacity
                    style={styles.permissionSecondaryBtn}
                    onPress={handlePickPhoto}
                    accessibilityRole="button"
                    accessibilityLabel="Choose photo from gallery instead"
                    activeOpacity={0.7}
                  >
                    <Ionicons
                      name="images-outline"
                      size={18}
                      color="#0D9488"
                      style={{ marginRight: 6 }}
                    />
                    <Text style={styles.permissionSecondaryBtnText} allowFontScaling>
                      Choose from Gallery Instead
                    </Text>
                  </TouchableOpacity>
                </View>
              ) : (
                <View style={styles.cameraSection}>
                  {/* Camera Viewfinder Viewport */}
                  <View style={styles.cameraViewport}>
                    <CameraView
                      ref={cameraRef}
                      style={StyleSheet.absoluteFill}
                      facing={facing}
                      mode="picture"
                      onMountError={(e) => {
                        console.warn("Camera mount error:", e);
                        setError("Camera error: " + (e?.message || "Could not initialize camera."));
                      }}
                    />

                    {/* Reticle / Framing Overlay (Sibling to prevent native layer clipping) */}
                    <View style={styles.reticleOverlay} pointerEvents="none">
                      <View style={styles.targetFrame}>
                        <View style={styles.targetBorderTL} />
                        <View style={styles.targetBorderTR} />
                        <View style={styles.targetBorderBL} />
                        <View style={styles.targetBorderBR} />
                        <View style={styles.targetPill}>
                          <Ionicons name="scan" size={13} color="#14B8A6" style={{ marginRight: 4 }} />
                          <Text style={styles.targetGuideText} allowFontScaling>
                            Align plate or meal inside frame
                          </Text>
                        </View>
                      </View>
                    </View>

                    {/* Top Corner: Camera Flip Button */}
                    <TouchableOpacity
                      style={styles.floatingFlipBtn}
                      onPress={() => setFacing((prev) => (prev === "back" ? "front" : "back"))}
                      accessibilityRole="button"
                      accessibilityLabel="Flip camera"
                      activeOpacity={0.7}
                    >
                      <Ionicons name="camera-reverse" size={20} color="#FFFFFF" />
                    </TouchableOpacity>
                  </View>

                  {/* Shutter & Controls Section (Completely OUTSIDE camera view for 100% visibility) */}
                  <View style={styles.controlsBar}>
                    {/* Gallery Button */}
                    <TouchableOpacity
                      style={styles.auxControlBtn}
                      onPress={handlePickPhoto}
                      accessibilityRole="button"
                      accessibilityLabel="Upload photo from gallery"
                      activeOpacity={0.7}
                    >
                      <View style={styles.auxIconCircle}>
                        <Ionicons name="images-outline" size={20} color="#0D9488" />
                      </View>
                      <Text style={styles.auxControlText} allowFontScaling>
                        Gallery
                      </Text>
                    </TouchableOpacity>

                    {/* Prominent Circular Capture Button */}
                    <TouchableOpacity
                      style={[
                        styles.shutterButton,
                        isCapturing && styles.shutterButtonDisabled,
                      ]}
                      onPress={handleCapturePhoto}
                      disabled={isCapturing}
                      accessibilityRole="button"
                      accessibilityLabel="Capture photo"
                      activeOpacity={0.8}
                    >
                      {isCapturing ? (
                        <ActivityIndicator size="small" color="#FFFFFF" />
                      ) : (
                        <View style={styles.shutterInnerCircle}>
                          <Ionicons name="camera" size={28} color="#FFFFFF" />
                        </View>
                      )}
                    </TouchableOpacity>

                    {/* Flip Camera Button */}
                    <TouchableOpacity
                      style={styles.auxControlBtn}
                      onPress={() => setFacing((prev) => (prev === "back" ? "front" : "back"))}
                      accessibilityRole="button"
                      accessibilityLabel="Switch camera"
                      activeOpacity={0.7}
                    >
                      <View style={styles.auxIconCircle}>
                        <Ionicons name="camera-reverse-outline" size={20} color="#0D9488" />
                      </View>
                      <Text style={styles.auxControlText} allowFontScaling>
                        Flip
                      </Text>
                    </TouchableOpacity>
                  </View>

                  {/* Primary Action Button directly below shutter */}
                  <TouchableOpacity
                    style={[
                      styles.primaryCaptureBtn,
                      isCapturing && styles.primaryCaptureBtnDisabled,
                    ]}
                    onPress={handleCapturePhoto}
                    disabled={isCapturing}
                    accessibilityRole="button"
                    accessibilityLabel="Take Photo and Analyze"
                    activeOpacity={0.85}
                  >
                    {isCapturing ? (
                      <>
                        <ActivityIndicator size="small" color="#FFFFFF" style={{ marginRight: 8 }} />
                        <Text style={styles.primaryCaptureBtnText} allowFontScaling>
                          Capturing…
                        </Text>
                      </>
                    ) : (
                      <>
                        <Ionicons name="camera" size={18} color="#FFFFFF" style={{ marginRight: 8 }} />
                        <Text style={styles.primaryCaptureBtnText} allowFontScaling>
                          Capture & Analyze Meal
                        </Text>
                      </>
                    )}
                  </TouchableOpacity>
                </View>
              )
            ) : null}

            {/* State 2: Photo Captured & Analyzing */}
            {photo && isAnalyzing ? (
              <View style={styles.analyzingSection}>
                <Image source={{ uri: photo.uri }} style={styles.previewImage} />
                <View style={styles.analyzingOverlay}>
                  <ActivityIndicator size="large" color="#0D9488" />
                  <Text style={styles.analyzingTitle} allowFontScaling>
                    Analyzing with Gemini AI…
                  </Text>
                  <Text style={styles.analyzingSubtitle} allowFontScaling>
                    Detecting dishes, estimating portions & glycemic impact
                  </Text>
                </View>
              </View>
            ) : null}

            {/* State 3: Analysis Result */}
            {photo && analysis && !isAnalyzing ? (
              <View style={styles.resultSection}>
                {/* Photo Preview Thumbnail */}
                <View style={styles.thumbnailRow}>
                  <Image source={{ uri: photo.uri }} style={styles.thumbnailImage} />
                  <View style={styles.thumbnailMeta}>
                    <View style={styles.aiBadge}>
                      <Ionicons
                        name="sparkles"
                        size={12}
                        color="#0D9488"
                        style={{ marginRight: 4 }}
                      />
                      <Text style={styles.aiBadgeText} allowFontScaling>
                        Gemini Vision AI
                      </Text>
                    </View>
                    <TouchableOpacity
                      style={styles.retakeBtn}
                      onPress={reset}
                      accessibilityRole="button"
                      accessibilityLabel="Retake meal photo"
                    >
                      <Ionicons
                        name="refresh"
                        size={13}
                        color="#64748B"
                        style={{ marginRight: 4 }}
                      />
                      <Text style={styles.retakeBtnText} allowFontScaling>
                        Retake Photo
                      </Text>
                    </TouchableOpacity>
                  </View>
                </View>

                {/* Detected Description */}
                <View style={styles.descriptionBox}>
                  <Text style={styles.descriptionLabel} allowFontScaling>
                    Detected Meal Description
                  </Text>
                  <Text style={styles.descriptionText} allowFontScaling>
                    {analysis.description}
                  </Text>
                </View>

                {/* Macro Chips */}
                <View style={styles.macrosRow}>
                  <View style={styles.macroCard}>
                    <Text style={styles.macroValue} allowFontScaling>
                      {analysis.total_calories_kcal}
                    </Text>
                    <Text style={styles.macroLabel} allowFontScaling>
                      Calories (kcal)
                    </Text>
                  </View>
                  <View style={styles.macroCard}>
                    <Text style={[styles.macroValue, { color: "#D97706" }]} allowFontScaling>
                      {analysis.total_carbs_g}g
                    </Text>
                    <Text style={styles.macroLabel} allowFontScaling>
                      Carbs
                    </Text>
                  </View>
                  <View style={styles.macroCard}>
                    <Text style={[styles.macroValue, { color: "#0D9488" }]} allowFontScaling>
                      {analysis.total_protein_g}g
                    </Text>
                    <Text style={styles.macroLabel} allowFontScaling>
                      Protein
                    </Text>
                  </View>
                  <View style={styles.macroCard}>
                    <Text
                      style={[
                        styles.macroValue,
                        {
                          color:
                            analysis.glycemic_impact === "LOW"
                              ? "#16A34A"
                              : analysis.glycemic_impact === "ELEVATED"
                              ? "#DC2626"
                              : "#0284C7",
                        },
                      ]}
                      allowFontScaling
                    >
                      {analysis.glycemic_impact || "MODERATE"}
                    </Text>
                    <Text style={styles.macroLabel} allowFontScaling>
                      Glycemic
                    </Text>
                  </View>
                </View>

                {/* Itemized Foods */}
                {analysis.items && analysis.items.length > 0 ? (
                  <View style={styles.itemsListContainer}>
                    <Text style={styles.itemsHeader} allowFontScaling>
                      Detected Foods ({analysis.items.length})
                    </Text>
                    {analysis.items.map((item, idx) => (
                      <View key={`${item.name}-${idx}`} style={styles.foodItemRow}>
                        <View style={styles.foodItemBullet} />
                        <Text style={styles.foodItemName} allowFontScaling>
                          {item.name}
                        </Text>
                        {item.portion_text ? (
                          <Text style={styles.foodItemPortion} allowFontScaling>
                            ({item.portion_text})
                          </Text>
                        ) : null}
                        <Text style={styles.foodItemCalories} allowFontScaling>
                          {item.calories_kcal} kcal
                        </Text>
                      </View>
                    ))}
                  </View>
                ) : null}

                {/* Hinglish Guidance Banner */}
                {analysis.patient_guidance_hinglish ? (
                  <View style={styles.guidanceBanner}>
                    <Ionicons
                      name="bulb-outline"
                      size={16}
                      color="#0D9488"
                      style={{ marginRight: 6, marginTop: 2 }}
                    />
                    <Text style={styles.guidanceText} allowFontScaling>
                      {analysis.patient_guidance_hinglish}
                    </Text>
                  </View>
                ) : null}

                {/* Save Actions */}
                <View style={styles.resultActions}>
                  <TouchableOpacity
                    style={styles.applyFormButton}
                    onPress={handleApplyDescription}
                    accessibilityRole="button"
                    accessibilityLabel="Add to meal form"
                    activeOpacity={0.8}
                  >
                    <Ionicons
                      name="clipboard-outline"
                      size={18}
                      color="#0D9488"
                      style={{ marginRight: 6 }}
                    />
                    <Text style={styles.applyFormButtonText} allowFontScaling>
                      Add to Meal Form
                    </Text>
                  </TouchableOpacity>

                  {onDirectLog ? (
                    <TouchableOpacity
                      style={[
                        styles.directLogButton,
                        isLogging && styles.directLogButtonDisabled,
                      ]}
                      onPress={handleDirectLog}
                      disabled={isLogging}
                      accessibilityRole="button"
                      accessibilityLabel="Save meal directly to diary"
                      activeOpacity={0.8}
                    >
                      {isLogging ? (
                        <ActivityIndicator size="small" color="#FFFFFF" />
                      ) : (
                        <>
                          <Ionicons
                            name="checkmark-done"
                            size={18}
                            color="#FFFFFF"
                            style={{ marginRight: 6 }}
                          />
                          <Text style={styles.directLogButtonText} allowFontScaling>
                            Log Directly to Diary
                          </Text>
                        </>
                      )}
                    </TouchableOpacity>
                  ) : null}
                </View>
              </View>
            ) : null}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.65)",
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.md,
  },
  modalCard: {
    width: "100%",
    maxWidth: 440,
    maxHeight: "94%",
    backgroundColor: "#FFFFFF",
    borderRadius: radii.xl,
    padding: spacing.lg,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 24,
    elevation: 8,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.sm,
  },
  headerTitles: {
    flex: 1,
  },
  title: {
    fontSize: 18,
    fontWeight: "700",
    color: "#0F172A",
  },
  subtitle: {
    fontSize: 12,
    color: "#64748B",
    marginTop: 2,
  },
  closeButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: "#F1F5F9",
    alignItems: "center",
    justifyContent: "center",
    marginLeft: spacing.sm,
  },
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FEF2F2",
    borderWidth: 1,
    borderColor: "#FECACA",
    borderRadius: radii.md,
    padding: spacing.sm,
    marginBottom: spacing.sm,
  },
  errorText: {
    flex: 1,
    fontSize: 12,
    color: "#B91C1C",
  },
  scrollArea: {
    maxHeight: 560,
  },
  scrollContent: {
    paddingBottom: spacing.sm,
  },
  cameraSection: {
    gap: spacing.sm,
  },
  cameraViewport: {
    width: "100%",
    height: 270,
    borderRadius: 18,
    overflow: "hidden",
    backgroundColor: "#000000",
    position: "relative",
  },
  reticleOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: "center",
    alignItems: "center",
  },
  floatingFlipBtn: {
    position: "absolute",
    top: 12,
    right: 12,
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: "rgba(15, 23, 42, 0.65)",
    alignItems: "center",
    justifyContent: "center",
  },
  targetFrame: {
    width: 200,
    height: 150,
    position: "relative",
    justifyContent: "center",
    alignItems: "center",
  },
  targetBorderTL: {
    position: "absolute",
    top: 0,
    left: 0,
    width: 24,
    height: 24,
    borderTopWidth: 3,
    borderLeftWidth: 3,
    borderColor: "#14B8A6",
    borderTopLeftRadius: 6,
  },
  targetBorderTR: {
    position: "absolute",
    top: 0,
    right: 0,
    width: 24,
    height: 24,
    borderTopWidth: 3,
    borderRightWidth: 3,
    borderColor: "#14B8A6",
    borderTopRightRadius: 6,
  },
  targetBorderBL: {
    position: "absolute",
    bottom: 0,
    left: 0,
    width: 24,
    height: 24,
    borderBottomWidth: 3,
    borderLeftWidth: 3,
    borderColor: "#14B8A6",
    borderBottomLeftRadius: 6,
  },
  targetBorderBR: {
    position: "absolute",
    bottom: 0,
    right: 0,
    width: 24,
    height: 24,
    borderBottomWidth: 3,
    borderRightWidth: 3,
    borderColor: "#14B8A6",
    borderBottomRightRadius: 6,
  },
  targetPill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(15, 23, 42, 0.65)",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  targetGuideText: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "600",
  },
  controlsBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-around",
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
  },
  auxControlBtn: {
    alignItems: "center",
    justifyContent: "center",
    width: 60,
    gap: 4,
  },
  auxIconCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: "#F0FDFA",
    borderWidth: 1,
    borderColor: "#CCFBF1",
    alignItems: "center",
    justifyContent: "center",
  },
  auxControlText: {
    fontSize: 11,
    fontWeight: "600",
    color: "#475569",
  },
  shutterButton: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: "#0D9488",
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 4,
    borderColor: "#CCFBF1",
    shadowColor: "#0D9488",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 10,
    elevation: 8,
  },
  shutterButtonDisabled: {
    opacity: 0.6,
  },
  shutterInnerCircle: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: "#0F766E",
    alignItems: "center",
    justifyContent: "center",
  },
  primaryCaptureBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#0D9488",
    paddingVertical: 12,
    borderRadius: radii.md,
    marginTop: 4,
  },
  primaryCaptureBtnDisabled: {
    opacity: 0.7,
  },
  primaryCaptureBtnText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "700",
  },
  permissionCard: {
    alignItems: "center",
    padding: spacing.lg,
    gap: spacing.md,
  },
  permissionIconCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: "#F0FDFA",
    alignItems: "center",
    justifyContent: "center",
  },
  permissionTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0F172A",
  },
  permissionSubtitle: {
    fontSize: 13,
    color: "#64748B",
    textAlign: "center",
    lineHeight: 18,
  },
  permissionButton: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#0D9488",
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: radii.md,
    marginTop: spacing.xs,
  },
  permissionButtonText: {
    fontSize: 14,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  permissionButtonSettings: {
    backgroundColor: "#0F766E",
  },
  settingsHintText: {
    fontSize: 12,
    color: "#64748B",
    textAlign: "center",
    lineHeight: 18,
    marginTop: 2,
  },
  permissionSecondaryBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: radii.md,
    backgroundColor: "#F0FDFA",
    borderWidth: 1,
    borderColor: "#CCFBF1",
    marginTop: 4,
  },
  permissionSecondaryBtnText: {
    fontSize: 13,
    fontWeight: "600",
    color: "#0D9488",
  },
  previewImage: {
    width: "100%",
    height: 240,
    borderRadius: 16,
    backgroundColor: "#F1F5F9",
  },
  analyzingSection: {
    borderRadius: 16,
    overflow: "hidden",
    position: "relative",
  },
  analyzingOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(15, 23, 42, 0.75)",
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.lg,
    gap: 8,
  },
  analyzingTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: "#FFFFFF",
    marginTop: 8,
  },
  analyzingSubtitle: {
    fontSize: 12,
    color: "#CBD5E1",
    textAlign: "center",
  },
  resultSection: {
    gap: spacing.md,
  },
  thumbnailRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: "#F8FAFC",
    padding: spacing.sm,
    borderRadius: radii.md,
  },
  thumbnailImage: {
    width: 56,
    height: 56,
    borderRadius: radii.sm,
    backgroundColor: "#E2E8F0",
  },
  thumbnailMeta: {
    flex: 1,
    gap: 4,
  },
  aiBadge: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    backgroundColor: "#F0FDFA",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#CCFBF1",
  },
  aiBadgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#0F766E",
  },
  retakeBtn: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    paddingVertical: 2,
  },
  retakeBtnText: {
    fontSize: 12,
    color: "#64748B",
    fontWeight: "500",
  },
  descriptionBox: {
    backgroundColor: "#F8FAFC",
    borderRadius: radii.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  descriptionLabel: {
    fontSize: 11,
    fontWeight: "700",
    color: "#64748B",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  descriptionText: {
    fontSize: 14,
    color: "#0F172A",
    fontWeight: "600",
    lineHeight: 20,
  },
  macrosRow: {
    flexDirection: "row",
    gap: spacing.xs,
  },
  macroCard: {
    flex: 1,
    backgroundColor: "#F8FAFC",
    borderRadius: radii.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.xs,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  macroValue: {
    fontSize: 15,
    fontWeight: "800",
    color: "#0F172A",
  },
  macroLabel: {
    fontSize: 10,
    fontWeight: "600",
    color: "#64748B",
    marginTop: 2,
  },
  itemsListContainer: {
    backgroundColor: "#F8FAFC",
    borderRadius: radii.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    gap: 8,
  },
  itemsHeader: {
    fontSize: 12,
    fontWeight: "700",
    color: "#475569",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  foodItemRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  foodItemBullet: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#0D9488",
  },
  foodItemName: {
    flex: 1,
    fontSize: 13,
    fontWeight: "600",
    color: "#1E293B",
  },
  foodItemPortion: {
    fontSize: 12,
    color: "#64748B",
  },
  foodItemCalories: {
    fontSize: 12,
    fontWeight: "700",
    color: "#0F766E",
  },
  guidanceBanner: {
    flexDirection: "row",
    alignItems: "flex-start",
    backgroundColor: "#F0FDFA",
    borderWidth: 1,
    borderColor: "#99F6E4",
    borderRadius: radii.md,
    padding: spacing.md,
  },
  guidanceText: {
    flex: 1,
    fontSize: 12,
    color: "#0F766E",
    fontWeight: "600",
    lineHeight: 18,
  },
  resultActions: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  applyFormButton: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1.5,
    borderColor: "#0D9488",
    backgroundColor: "#FFFFFF",
  },
  applyFormButtonText: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0D9488",
  },
  directLogButton: {
    flex: 1.2,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.md,
    borderRadius: radii.md,
    backgroundColor: "#0D9488",
  },
  directLogButtonDisabled: {
    opacity: 0.7,
  },
  directLogButtonText: {
    fontSize: 13,
    fontWeight: "700",
    color: "#FFFFFF",
  },
});
