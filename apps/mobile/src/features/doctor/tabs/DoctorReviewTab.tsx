import React, { useState } from "react";
import {
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { touchTarget } from "../../../theming/tokens";
import {
  doctorPalette,
  doctorRadii,
  doctorSoftShadow,
  doctorPillShadow,
} from "../doctorDesign";
import { useReviewQueue } from "../useReviewQueue";
import { ArtifactDetailScreen } from "../ArtifactDetailScreen";
import type { AIArtifactResponse } from "../../../services/schemas/ai";

export type DoctorReviewTabProps = {
  onOpenPatientById?: (patientId: string) => void;
};

export function DoctorReviewTab({ onOpenPatientById }: DoctorReviewTabProps) {
  const { queue, artifactCount, isLoading, refetch } = useReviewQueue();
  const [selectedArtifact, setSelectedArtifact] = useState<AIArtifactResponse | null>(null);
  const [kindFilter, setKindFilter] = useState<string>("all");
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handlePullToRefresh = async () => {
    setIsRefreshing(true);
    try {
      await refetch();
    } finally {
      setIsRefreshing(false);
    }
  };

  if (selectedArtifact) {
    return (
      <ArtifactDetailScreen
        artifactId={selectedArtifact.artifact_id}
        onBack={() => {
          setSelectedArtifact(null);
          refetch();
        }}
      />
    );
  }

  const items = queue.filter((item: AIArtifactResponse) => {
    if (kindFilter === "all") return true;
    return item.artifact_kind === kindFilter;
  });

  const getKindIcon = (
    kind: string
  ): React.ComponentProps<typeof Ionicons>["name"] => {
    if (kind.includes("meal")) return "restaurant";
    if (kind.includes("glucose")) return "water";
    return "sparkles";
  };

  return (
    <View style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing || isLoading}
            onRefresh={handlePullToRefresh}
            tintColor={doctorPalette.primary}
            colors={[doctorPalette.primary]}
          />
        }
      >
        {/* Clinician Approval Boundary Notice Card */}
        <View style={styles.boundaryNotice}>
          <View style={styles.boundaryIconBox}>
            <Ionicons name="shield-checkmark" size={20} color={doctorPalette.primary} />
          </View>
          <View style={styles.boundaryTextCol}>
            <Text style={styles.boundaryTitle} allowFontScaling>
              Clinician Sign-off Required
            </Text>
            <Text style={styles.boundarySubtext} allowFontScaling>
              AI models provide assistive suggestions only. Every observation requires explicit
              human doctor verification.
            </Text>
          </View>
        </View>

        {/* Filter Chips */}
        <View style={styles.filtersRow}>
          {[
            { key: "all", label: `All (${artifactCount})` },
            { key: "meal_review", label: "Meal Scans" },
            { key: "glucose_review", label: "Glucose Alerts" },
            { key: "report_summary", label: "Reports" },
          ].map((tab) => {
            const active = kindFilter === tab.key;
            return (
              <Pressable
                key={tab.key}
                style={[styles.filterChip, active ? styles.filterChipActive : null]}
                onPress={() => setKindFilter(tab.key)}
                accessibilityRole="button"
                accessibilityLabel={`Filter by ${tab.label}`}
              >
                <Text
                  style={[styles.filterChipText, active ? styles.filterChipTextActive : null]}
                  allowFontScaling
                >
                  {tab.label}
                </Text>
              </Pressable>
            );
          })}
        </View>

        {/* Items List */}
        {items.length > 0 ? (
          <View style={styles.list}>
            {items.map((item) => (
              <View key={item.artifact_id} style={styles.card}>
                <View style={styles.cardTop}>
                  <View style={styles.kindIconBox}>
                    <Ionicons
                      name={getKindIcon(item.artifact_kind)}
                      size={20}
                      color={doctorPalette.primary}
                    />
                  </View>
                  <View style={styles.cardHeaderInfo}>
                    <View style={styles.kindRow}>
                      <Text style={styles.kindLabel} allowFontScaling>
                        {item.artifact_kind.replace("_", " ").toUpperCase()}
                      </Text>
                      <View style={styles.pendingBadge}>
                        <Text style={styles.pendingBadgeText} allowFontScaling>
                          PENDING
                        </Text>
                      </View>
                    </View>
                    <Text style={styles.timestamp} allowFontScaling>
                      {new Date(item.created_at).toLocaleString()}
                    </Text>
                  </View>
                </View>

                <Text style={styles.summaryText} allowFontScaling>
                  {item.summary}
                </Text>

                <View style={styles.cardFooter}>
                  <View style={styles.patientMeta}>
                    <Text style={styles.patientLabel} allowFontScaling>
                      Patient:
                    </Text>
                    <Text style={styles.patientId} allowFontScaling>
                      {item.patient_id.slice(0, 8)}…
                    </Text>
                    {onOpenPatientById ? (
                      <TouchableOpacity
                        onPress={() => onOpenPatientById(item.patient_id)}
                        accessibilityRole="button"
                        accessibilityLabel={`Open patient record for ID ${item.patient_id}`}
                      >
                        <Text style={styles.openPatientText} allowFontScaling>
                          View Record →
                        </Text>
                      </TouchableOpacity>
                    ) : null}
                  </View>

                  <TouchableOpacity
                    style={styles.reviewButton}
                    onPress={() => setSelectedArtifact(item)}
                    accessibilityRole="button"
                    accessibilityLabel={`Inspect and sign artifact ${item.artifact_id}`}
                    activeOpacity={0.85}
                  >
                    <Text style={styles.reviewButtonText} allowFontScaling>
                      Inspect & Sign
                    </Text>
                    <Ionicons name="arrow-forward" size={13} color="#FFFFFF" />
                  </TouchableOpacity>
                </View>
              </View>
            ))}
          </View>
        ) : (
          <View style={styles.emptyCard}>
            <View style={styles.emptyIconBox}>
              <Ionicons name="checkmark-done-circle" size={36} color="#10B981" />
            </View>
            <Text style={styles.emptyTitle} allowFontScaling>
              Review Queue Empty
            </Text>
            <Text style={styles.emptySubtitle} allowFontScaling>
              All machine-generated dietary analyses, glucose excursions, and model recommendations
              have been signed off.
            </Text>
          </View>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: doctorPalette.appBackground,
  },
  content: {
    paddingHorizontal: 20,
    paddingTop: 4,
    gap: 16,
    paddingBottom: 130,
  },
  boundaryNotice: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: doctorPalette.surface,
    borderRadius: 22,
    padding: 16,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    ...doctorSoftShadow,
  },
  boundaryIconBox: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: doctorPalette.surfaceBlue,
    alignItems: "center",
    justifyContent: "center",
  },
  boundaryTextCol: {
    flex: 1,
  },
  boundaryTitle: {
    fontSize: 14,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  boundarySubtext: {
    fontSize: 12,
    color: doctorPalette.muted,
    marginTop: 2,
    lineHeight: 16,
  },
  filtersRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  filterChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: doctorRadii.pill,
    backgroundColor: doctorPalette.surface,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    ...doctorSoftShadow,
  },
  filterChipActive: {
    backgroundColor: doctorPalette.surfaceLime,
    borderColor: doctorPalette.limeBorder,
  },
  filterChipText: {
    fontSize: 12,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  filterChipTextActive: {
    color: doctorPalette.ink,
    fontWeight: "800",
  },
  list: {
    gap: 12,
  },
  card: {
    backgroundColor: doctorPalette.surface,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    padding: 18,
    gap: 12,
    ...doctorSoftShadow,
  },
  cardTop: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  kindIconBox: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: doctorPalette.surfaceBlue,
    alignItems: "center",
    justifyContent: "center",
  },
  cardHeaderInfo: {
    flex: 1,
  },
  kindRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  kindLabel: {
    fontSize: 12,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  pendingBadge: {
    backgroundColor: "#FEF3C7",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: doctorRadii.pill,
  },
  pendingBadgeText: {
    fontSize: 9,
    fontWeight: "800",
    color: "#B45309",
  },
  timestamp: {
    fontSize: 11,
    color: doctorPalette.muted,
    marginTop: 2,
  },
  summaryText: {
    fontSize: 13,
    color: doctorPalette.ink,
    lineHeight: 20,
  },
  cardFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderTopWidth: 1,
    borderTopColor: doctorPalette.borderSubtle,
    paddingTop: 12,
    marginTop: 2,
  },
  patientMeta: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    flexShrink: 1,
  },
  patientLabel: {
    fontSize: 11,
    color: doctorPalette.muted,
  },
  patientId: {
    fontSize: 12,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  openPatientText: {
    fontSize: 11,
    fontWeight: "800",
    color: doctorPalette.primary,
    marginLeft: 4,
  },
  reviewButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: doctorPalette.primary,
    borderRadius: doctorRadii.pill,
    minHeight: touchTarget.min,
    paddingHorizontal: 16,
    justifyContent: "center",
    ...doctorPillShadow,
  },
  reviewButtonText: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "800",
  },
  emptyCard: {
    backgroundColor: doctorPalette.surface,
    borderRadius: 24,
    padding: 32,
    alignItems: "center",
    gap: 10,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    marginTop: 8,
    ...doctorSoftShadow,
  },
  emptyIconBox: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: doctorPalette.limeSoft,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 4,
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  emptySubtitle: {
    fontSize: 13,
    color: doctorPalette.muted,
    textAlign: "center",
    lineHeight: 18,
    maxWidth: 290,
  },
});
