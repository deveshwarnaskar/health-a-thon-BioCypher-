export type SupportedLanguage = "en" | "hi" | "bn" | "ta" | "te" | "mr";

export interface LanguageInfo {
  code: SupportedLanguage;
  name: string;
  nativeName: string;
}

export const SUPPORTED_LANGUAGES: Record<SupportedLanguage, LanguageInfo> = {
  en: { code: "en", name: "English", nativeName: "English" },
  hi: { code: "hi", name: "Hindi", nativeName: "हिन्दी" },
  bn: { code: "bn", name: "Bengali", nativeName: "বাংলা" },
  ta: { code: "ta", name: "Tamil", nativeName: "தமிழ்" },
  te: { code: "te", name: "Telugu", nativeName: "తెలుగు" },
  mr: { code: "mr", name: "Marathi", nativeName: "मराठी" },
};

export interface TranslationDictionary {
  common: {
    appName: string;
    save: string;
    cancel: string;
    confirm: string;
    retry: string;
    delete: string;
    close: string;
    back: string;
    loading: string;
    error: string;
    offline: string;
    online: string;
    savedLocally: string;
  };
  sync: {
    savedLocally: string;
    waitingToSync: string;
    syncing: string;
    synced: string;
    needsAttention: string;
    offlineBanner: string;
    reconnectPrompt: string;
  };
  roles: {
    doctor: string;
    nurse: string;
    caregiver: string;
    dietitian: string;
    fieldHealthWorker: string;
    coordinator: string;
    patient: string;
  };
  glucose: {
    title: string;
    record: string;
    valueLabel: string;
    fasting: string;
    postPrandial: string;
    random: string;
    bedtime: string;
    history: string;
    validationError: string;
    localSaveNotice: string;
  };
  meals: {
    title: string;
    record: string;
    descriptionLabel: string;
    portionSize: string;
    katoriSmall: string;
    katoriMedium: string;
    katoriLarge: string;
    quantity: string;
    localSaveNotice: string;
  };
  tasks: {
    title: string;
    start: string;
    complete: string;
    reassign: string;
    statusOpen: string;
    statusInProgress: string;
    statusCompleted: string;
    conflictNotice: string;
  };
  ai: {
    onlineOnlyNotice: string;
    reviewQueue: string;
    approved: string;
    rejected: string;
  };
  medication: {
    readOnlyNotice: string;
    currentPlan: string;
  };
  accessibility: {
    syncStatusLabel: string;
    offlineModeActive: string;
    networkRestored: string;
    increaseTextNotice: string;
  };
  whatsapp: {
    modalTitle: string;
    modalSubtitle: string;
    benefit1: string;
    benefit2: string;
    benefit3: string;
    connectButton: string;
    maybeLaterButton: string;
    homeReminderTitle: string;
    homeReminderSubtitle: string;
    homeConnectAction: string;
    flowStep1Title: string;
    flowStep1Subtitle: string;
    phoneLabel: string;
    sendOtpButton: string;
    flowStep2Title: string;
    flowStep2Subtitle: string;
    codeLabel: string;
    verifyButton: string;
    resendButton: string;
    flowStep3Title: string;
    flowStep3Subtitle: string;
    doneButton: string;
    settingsSectionTitle: string;
    connectedStatus: string;
    notConnectedStatus: string;
    connectedDesc: string;
    notConnectedDesc: string;
    manageButton: string;
    manageTitle: string;
    linkedNumberLabel: string;
    connectedSinceLabel: string;
    supportedFeaturesTitle: string;
    featureHealthLogging: string;
    featureFoodLogging: string;
    featureVoiceNotes: string;
    disconnectButton: string;
    disconnectConfirmTitle: string;
    disconnectConfirmMessage: string;
    confirmDisconnect: string;
    cancel: string;
    statusUnavailableOffline: string;
  };
}
