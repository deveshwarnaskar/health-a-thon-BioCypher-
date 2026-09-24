import React, { useState } from "react";
import {
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { touchTarget } from "../../../theming/tokens";
import {
  doctorPalette,
  doctorRadii,
  doctorSoftShadow,
} from "../doctorDesign";
import type { PatientSummaryResponse } from "../../../services/schemas/patients";

export type DoctorPatientsTabProps = {
  patients: PatientSummaryResponse[];
  isLoading: boolean;
  onRefresh: () => Promise<void> | void;
  onSelectPatient: (patient: PatientSummaryResponse) => void;
};

export function DoctorPatientsTab({
  patients,
  isLoading,
  onRefresh,
  onSelectPatient,
}: DoctorPatientsTabProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [filterMode, setFilterMode] = useState<"all" | "active" | "inactive">("all");
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handlePullToRefresh = async () => {
    setIsRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setIsRefreshing(false);
    }
  };

  const activeCount = patients.filter((p) => p.active).length;
  const inactiveCount = patients.filter((p) => !p.active).length;

  const filteredPatients = patients
    .filter((p) => {
      const q = searchQuery.toLowerCase().trim();
      const matchesQuery =
        !q ||
        p.name.toLowerCase().includes(q) ||
        p.uh_id.toLowerCase().includes(q) ||
        (p.facility_id ? p.facility_id.toLowerCase().includes(q) : false);
      if (!matchesQuery) return false;
      if (filterMode === "active") return p.active;
      if (filterMode === "inactive") return !p.active;
      return true;
    })
    .sort((a, b) => a.name.localeCompare(b.name));

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
        {/* Patient Cohort Overview Banner */}
        <View style={styles.cohortSummaryCard}>
          <View style={styles.cohortSummaryTop}>
            <View style={styles.cohortIconWrap}>
              <Ionicons name="people" size={20} color={doctorPalette.primary} />
            </View>
            <View style={styles.cohortTextCol}>
              <Text style={styles.cohortTitle} allowFontScaling numberOfLines={1}>
                {patients.length} {patients.length === 1 ? "Patient" : "Patients"} Enrolled
              </Text>
              <Text style={styles.cohortSubtitle} allowFontScaling numberOfLines={1}>
                Apex Diabetes Care Centre · Outpatient Surveillance
              </Text>
            </View>
          </View>
          <View style={styles.cohortStatsRow}>
            <View style={styles.cohortStatCol}>
              <Text style={styles.cohortStatNum} allowFontScaling>{patients.length}</Text>
              <Text style={styles.cohortStatLabel} allowFontScaling>Total Linked</Text>
            </View>
            <View style={styles.cohortStatDivider} />
            <View style={styles.cohortStatCol}>
              <Text style={[styles.cohortStatNum, { color: "#166534" }]} allowFontScaling>{activeCount}</Text>
              <Text style={styles.cohortStatLabel} allowFontScaling>Active Monitoring</Text>
            </View>
            <View style={styles.cohortStatDivider} />
            <View style={styles.cohortStatCol}>
              <Text style={[styles.cohortStatNum, { color: inactiveCount > 0 ? "#B45309" : doctorPalette.muted }]} allowFontScaling>
                {inactiveCount}
              </Text>
              <Text style={styles.cohortStatLabel} allowFontScaling>Inactive</Text>
            </View>
          </View>
        </View>

        {/* Floating Modern Search Bar */}
        <View style={styles.searchBar}>
          <Ionicons name="search" size={20} color={doctorPalette.muted} style={styles.searchIcon} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search by name, UHID, or facility…"
            placeholderTextColor={doctorPalette.quiet}
            value={searchQuery}
            onChangeText={setSearchQuery}
            autoCapitalize="none"
            autoCorrect={false}
          />
          {searchQuery ? (
            <TouchableOpacity
              onPress={() => setSearchQuery("")}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
              accessibilityRole="button"
              accessibilityLabel="Clear search text"
            >
              <Ionicons name="close-circle" size={18} color={doctorPalette.muted} />
            </TouchableOpacity>
          ) : null}
        </View>

        {/* Filter Pills */}
        <View style={styles.filtersRow}>
          <Pressable
            style={[styles.filterChip, filterMode === "all" ? styles.filterChipActive : null]}
            onPress={() => setFilterMode("all")}
            accessibilityRole="button"
            accessibilityLabel={`Filter all patients: ${patients.length}`}
          >
            <Text
              style={[
                styles.filterChipText,
                filterMode === "all" ? styles.filterChipTextActive : null,
              ]}
              allowFontScaling
            >
              All ({patients.length})
            </Text>
          </Pressable>

          <Pressable
            style={[styles.filterChip, filterMode === "active" ? styles.filterChipActive : null]}
            onPress={() => setFilterMode("active")}
            accessibilityRole="button"
            accessibilityLabel={`Filter active patients: ${activeCount}`}
          >
            <Text
              style={[
                styles.filterChipText,
                filterMode === "active" ? styles.filterChipTextActive : null,
              ]}
              allowFontScaling
            >
              Active ({activeCount})
            </Text>
          </Pressable>

          <Pressable
            style={[styles.filterChip, filterMode === "inactive" ? styles.filterChipActive : null]}
            onPress={() => setFilterMode("inactive")}
            accessibilityRole="button"
            accessibilityLabel={`Filter inactive patients: ${inactiveCount}`}
          >
            <Text
              style={[
                styles.filterChipText,
                filterMode === "inactive" ? styles.filterChipTextActive : null,
              ]}
              allowFontScaling
            >
              Inactive ({inactiveCount})
            </Text>
          </Pressable>
        </View>

        {/* Patients List */}
        {filteredPatients.length > 0 ? (
          <View style={styles.list}>
            {filteredPatients.map((patient) => (
              <TouchableOpacity
                key={patient.patient_id}
                style={styles.patientCard}
                onPress={() => onSelectPatient(patient)}
                accessibilityRole="button"
                accessibilityLabel={`Open patient record for ${patient.name}, UHID ${patient.uh_id}`}
                activeOpacity={0.75}
              >
                <View style={styles.avatarCircle}>
                  <Text style={styles.avatarText} allowFontScaling>
                    {patient.name.charAt(0).toUpperCase()}
                  </Text>
                </View>

                <View style={styles.infoCol}>
                  <View style={styles.nameRow}>
                    <Text style={styles.patientName} numberOfLines={1} allowFontScaling>
                      {patient.name}
                    </Text>
                    {patient.active ? (
                      <Ionicons name="checkmark-circle" size={15} color={doctorPalette.primary} />
                    ) : null}
                  </View>
                  <Text style={styles.patientMeta} allowFontScaling>
                    UHID: {patient.uh_id} · {patient.facility_id}
                  </Text>

                  <View style={styles.badgeRow}>
                    <View
                      style={[
                        styles.statusBadge,
                        patient.active ? styles.statusBadgeActive : styles.statusBadgeInactive,
                      ]}
                    >
                      <Text
                        style={[
                          styles.statusBadgeText,
                          patient.active
                            ? styles.statusBadgeTextActive
                            : styles.statusBadgeTextInactive,
                        ]}
                        allowFontScaling
                      >
                        {patient.active ? "Active Monitored" : "Inactive"}
                      </Text>
                    </View>
                  </View>
                </View>

                {/* Circular Arrow Button */}
                <View style={styles.circleArrowBtn}>
                  <Ionicons name="arrow-forward" size={16} color={doctorPalette.ink} />
                </View>
              </TouchableOpacity>
            ))}
          </View>
        ) : (
          <View style={styles.emptyCard}>
            <Ionicons name="search-outline" size={36} color={doctorPalette.muted} />
            <Text style={styles.emptyTitle} allowFontScaling>
              No matching patients
            </Text>
            <Text style={styles.emptySub} allowFontScaling>
              {searchQuery
                ? `No patients match "${searchQuery}". Try searching by another keyword.`
                : "No patients found in this filter."}
            </Text>
            {searchQuery ? (
              <TouchableOpacity
                style={styles.clearSearchBtn}
                onPress={() => setSearchQuery("")}
                accessibilityRole="button"
                accessibilityLabel="Reset search query"
              >
                <Text style={styles.clearSearchText} allowFontScaling>
                  Clear search
                </Text>
              </TouchableOpacity>
            ) : null}
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
  searchBar: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.pill,
    paddingHorizontal: 16,
    height: 50,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    ...doctorSoftShadow,
  },
  searchIcon: {
    marginRight: 10,
  },
  searchInput: {
    flex: 1,
    fontSize: 14,
    color: doctorPalette.ink,
    paddingVertical: 8,
  },
  filtersRow: {
    flexDirection: "row",
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
  patientCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    backgroundColor: doctorPalette.surface,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    padding: 16,
    ...doctorSoftShadow,
  },
  avatarCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: doctorPalette.surfaceBlue,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "#DBEAFE",
  },
  avatarText: {
    fontSize: 18,
    fontWeight: "800",
    color: doctorPalette.primary,
  },
  infoCol: {
    flex: 1,
  },
  nameRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  patientName: {
    fontSize: 16,
    fontWeight: "800",
    color: doctorPalette.ink,
    flexShrink: 1,
  },
  patientMeta: {
    fontSize: 12,
    color: doctorPalette.muted,
    marginTop: 2,
  },
  badgeRow: {
    flexDirection: "row",
    marginTop: 6,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: doctorRadii.pill,
  },
  statusBadgeActive: {
    backgroundColor: doctorPalette.limeSoft,
  },
  statusBadgeInactive: {
    backgroundColor: "#F1F5F9",
  },
  statusBadgeText: {
    fontSize: 10,
    fontWeight: "700",
  },
  statusBadgeTextActive: {
    color: "#15803D",
  },
  statusBadgeTextInactive: {
    color: "#64748B",
  },
  circleArrowBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: doctorPalette.appBackground,
    alignItems: "center",
    justifyContent: "center",
  },
  emptyCard: {
    backgroundColor: doctorPalette.surface,
    borderRadius: 24,
    padding: 28,
    alignItems: "center",
    gap: 8,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    marginTop: 8,
    ...doctorSoftShadow,
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: doctorPalette.ink,
    marginTop: 4,
  },
  emptySub: {
    fontSize: 13,
    color: doctorPalette.muted,
    textAlign: "center",
    maxWidth: 280,
  },
  clearSearchBtn: {
    marginTop: 10,
    backgroundColor: doctorPalette.surfaceLime,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: doctorRadii.pill,
  },
  clearSearchText: {
    fontSize: 12,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  cohortSummaryCard: {
    backgroundColor: doctorPalette.surface,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: doctorPalette.borderSubtle,
    padding: 16,
    gap: 14,
    ...doctorSoftShadow,
  },
  cohortSummaryTop: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  cohortIconWrap: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: doctorPalette.surfaceBlue,
    alignItems: "center",
    justifyContent: "center",
  },
  cohortTextCol: {
    flex: 1,
    gap: 2,
  },
  cohortTitle: {
    fontSize: 15,
    fontWeight: "800",
    color: doctorPalette.ink,
    letterSpacing: -0.2,
  },
  cohortSubtitle: {
    fontSize: 11,
    fontWeight: "600",
    color: doctorPalette.muted,
  },
  cohortStatsRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: doctorPalette.surfaceSoft,
    borderRadius: doctorRadii.md,
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  cohortStatCol: {
    flex: 1,
    alignItems: "center",
    gap: 2,
  },
  cohortStatNum: {
    fontSize: 16,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  cohortStatLabel: {
    fontSize: 10,
    fontWeight: "700",
    color: doctorPalette.muted,
  },
  cohortStatDivider: {
    width: 1,
    height: 22,
    backgroundColor: doctorPalette.borderSubtle,
  },
});
