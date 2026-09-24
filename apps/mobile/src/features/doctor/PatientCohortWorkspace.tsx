import React, { useState } from "react";
import { StyleSheet, Text, View, TextInput, Pressable, ScrollView, useWindowDimensions } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Badge } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { LoadingState } from "../../components/primitives/LoadingState";
import { EmptyState } from "../../components/primitives/EmptyState";
import { spacing, typography } from "../../theming/tokens";
import { doctorPalette, doctorRadii, doctorSoftShadow } from "./doctorDesign";
import type { PatientSummaryResponse } from "../../services/schemas/patients";

export type PatientCohortWorkspaceProps = {
  patients: PatientSummaryResponse[];
  isLoading: boolean;
  onSelectPatient: (patient: PatientSummaryResponse) => void;
  onRefresh?: () => void;
};

export function PatientCohortWorkspace({
  patients,
  isLoading,
  onSelectPatient,
  onRefresh,
}: PatientCohortWorkspaceProps) {
  const { width } = useWindowDimensions();
  const isCompact = width < 760;
  const [query, setQuery] = useState("");
  const [filterActive, setFilterActive] = useState<"all" | "active" | "inactive">("all");
  const [sortBy, setSortBy] = useState<"name" | "uhid">("name");

  const filtered = patients
    .filter((p) => {
      const matchesQuery =
        p.name.toLowerCase().includes(query.toLowerCase()) ||
        p.uh_id.toLowerCase().includes(query.toLowerCase());
      if (!matchesQuery) return false;
      if (filterActive === "active") return p.active;
      if (filterActive === "inactive") return !p.active;
      return true;
    })
    .sort((a, b) => {
      if (sortBy === "name") return a.name.localeCompare(b.name);
      return a.uh_id.localeCompare(b.uh_id);
    });

  return (
    <View style={styles.container}>
      {/* Header bar */}
      <View style={[styles.header, isCompact ? styles.headerCompact : null]}>
        <View>
          <Text style={styles.title}>Patient Directory</Text>
          <Text style={styles.subtitle}>
            Authorized facility cohort ({patients.length} total patients)
          </Text>
        </View>
        {onRefresh ? (
          <Button label="Refresh Cohort" variant="outline" onPress={onRefresh} />
        ) : null}
      </View>

      {/* Filter and Search Bar */}
      <View style={[styles.toolbar, isCompact ? styles.toolbarCompact : null]}>
        <View style={styles.searchBox}>
          <Ionicons name="search" size={18} color={doctorPalette.quiet} style={styles.searchIcon} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search by name or UHID…"
            placeholderTextColor={doctorPalette.quiet}
            value={query}
            onChangeText={setQuery}
            autoCapitalize="none"
            autoCorrect={false}
          />
          {query ? (
            <Pressable
              onPress={() => setQuery("")}
              hitSlop={8}
              accessibilityRole="button"
              accessibilityLabel="Clear patient search"
            >
              <Ionicons name="close" size={16} color={doctorPalette.muted} />
            </Pressable>
          ) : null}
        </View>

        {/* Filter Pills */}
        <View style={styles.filters}>
          <Pressable
            style={[styles.filterChip, filterActive === "all" ? styles.filterChipActive : null]}
            onPress={() => setFilterActive("all")}
          >
            <Text style={[styles.filterText, filterActive === "all" ? styles.filterTextActive : null]}>
              All ({patients.length})
            </Text>
          </Pressable>
          <Pressable
            style={[styles.filterChip, filterActive === "active" ? styles.filterChipActive : null]}
            onPress={() => setFilterActive("active")}
          >
            <Text style={[styles.filterText, filterActive === "active" ? styles.filterTextActive : null]}>
              Active ({patients.filter((p) => p.active).length})
            </Text>
          </Pressable>
          <Pressable
            style={[styles.filterChip, filterActive === "inactive" ? styles.filterChipActive : null]}
            onPress={() => setFilterActive("inactive")}
          >
            <Text style={[styles.filterText, filterActive === "inactive" ? styles.filterTextActive : null]}>
              Inactive ({patients.filter((p) => !p.active).length})
            </Text>
          </Pressable>
        </View>

        {/* Sort */}
        <View style={styles.sortBox}>
          <Text style={styles.sortLabel}>Sort:</Text>
          <Pressable onPress={() => setSortBy(sortBy === "name" ? "uhid" : "name")}>
            <Text style={styles.sortBtnText}>{sortBy === "name" ? "Name (A-Z)" : "UHID"}</Text>
          </Pressable>
        </View>
      </View>

      {/* Content */}
      {isLoading ? (
        <LoadingState label="Loading patient directory…" />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No patients found"
          message={query ? "No patients match your search criteria." : "No patients in facility cohort."}
        />
      ) : (
        <ScrollView style={styles.tableScroll} contentContainerStyle={styles.tableContent}>
          {/* Table Header */}
          {!isCompact ? (
            <View style={styles.tableHeaderRow}>
              <Text style={[styles.thText, styles.patientNameCell]}>PATIENT NAME</Text>
              <Text style={[styles.thText, styles.patientUhidCell]}>UHID</Text>
              <Text style={[styles.thText, styles.statusCell]}>STATUS</Text>
              <Text style={[styles.thText, styles.enrolledCell]}>ENROLLED</Text>
              <Text style={[styles.thText, styles.actionCell, styles.actionHeaderText]}>ACTION</Text>
            </View>
          ) : null}

          {/* Rows */}
          {filtered.map((patient) => (
            <Pressable
              key={patient.patient_id}
              style={[styles.tableRow, isCompact ? styles.tableRowCompact : null]}
              onPress={() => onSelectPatient(patient)}
            >
              <View style={[styles.tdCell, isCompact ? styles.patientIdentityCompact : styles.patientNameCell]}>
                <View style={styles.avatarMini}>
                  <Text style={styles.avatarMiniText}>{patient.name.charAt(0)}</Text>
                </View>
                <View>
                  <Text style={styles.rowName}>{patient.name}</Text>
                  <Text style={styles.rowSub}>ID: {patient.patient_id.slice(0, 8)}…</Text>
                </View>
              </View>

              <View style={[styles.tdCell, isCompact ? styles.patientMetaCompact : styles.patientUhidCell]}>
                <Text style={styles.rowUhid}>{patient.uh_id}</Text>
              </View>

              <View style={[styles.tdCell, isCompact ? styles.patientMetaCompact : styles.statusCell]}>
                <Badge
                  label={patient.active ? "Active" : "Inactive"}
                  tone={patient.active ? "success" : "neutral"}
                />
              </View>

              <View style={[styles.tdCell, isCompact ? styles.patientMetaCompact : styles.enrolledCell]}>
                <Text style={styles.rowDate}>
                  {patient.created_at ? new Date(patient.created_at).toLocaleDateString() : "—"}
                </Text>
              </View>

              <View style={[styles.tdCell, isCompact ? styles.patientActionCompact : styles.actionCell]}>
                <Button
                  label="Open"
                  variant="primary"
                  onPress={() => onSelectPatient(patient)}
                />
              </View>
            </Pressable>
          ))}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: doctorPalette.surfaceSoft,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
    gap: spacing.md,
  },
  headerCompact: {
    alignItems: "flex-start",
    flexWrap: "wrap",
  },
  title: {
    fontSize: 28,
    lineHeight: 34,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  subtitle: {
    fontSize: typography.fontSize.bodySmall,
    color: doctorPalette.muted,
    fontWeight: "600",
  },
  toolbar: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    backgroundColor: doctorPalette.surface,
    borderBottomWidth: 1,
    borderBottomColor: doctorPalette.border,
    flexWrap: "wrap",
  },
  toolbarCompact: {
    alignItems: "stretch",
  },
  searchBox: {
    flex: 1,
    minWidth: 220,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: doctorPalette.surfaceSoft,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    borderRadius: doctorRadii.pill,
    paddingHorizontal: spacing.sm,
    height: 46,
  },
  searchIcon: {
    marginRight: 6,
  },
  searchInput: {
    flex: 1,
    fontSize: typography.fontSize.bodySmall,
    color: doctorPalette.ink,
    paddingVertical: 0,
  },
  filters: {
    flexDirection: "row",
    gap: 6,
  },
  filterChip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: doctorRadii.pill,
    backgroundColor: doctorPalette.surfaceSoft,
    borderWidth: 1,
    borderColor: doctorPalette.border,
  },
  filterChipActive: {
    backgroundColor: doctorPalette.surfaceLime,
    borderColor: doctorPalette.surfaceLime,
  },
  filterText: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
    fontWeight: "700",
  },
  filterTextActive: {
    color: doctorPalette.ink,
    fontWeight: "800",
  },
  sortBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  sortLabel: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
  },
  sortBtnText: {
    fontSize: typography.fontSize.caption,
    fontWeight: "700",
    color: doctorPalette.primary,
  },
  tableScroll: {
    flex: 1,
  },
  tableContent: {
    padding: spacing.lg,
    gap: spacing.sm,
  },
  tableHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: doctorPalette.surface,
    borderRadius: doctorRadii.lg,
    borderWidth: 1,
    borderColor: doctorPalette.border,
  },
  thText: {
    fontSize: 11,
    fontWeight: "800",
    color: doctorPalette.quiet,
    letterSpacing: 0,
  },
  tableRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    backgroundColor: doctorPalette.surface,
    borderWidth: 1,
    borderColor: doctorPalette.border,
    borderRadius: doctorRadii.lg,
    ...doctorSoftShadow,
  },
  tableRowCompact: {
    flexDirection: "column",
    alignItems: "stretch",
    gap: spacing.sm,
  },
  tdCell: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  patientNameCell: {
    flex: 2,
  },
  patientUhidCell: {
    flex: 1.2,
  },
  statusCell: {
    flex: 1,
  },
  enrolledCell: {
    flex: 1.5,
  },
  actionCell: {
    flex: 1.2,
    justifyContent: "flex-end",
  },
  actionHeaderText: {
    textAlign: "right",
  },
  patientIdentityCompact: {
    width: "100%",
  },
  patientMetaCompact: {
    alignSelf: "flex-start",
  },
  patientActionCompact: {
    alignSelf: "stretch",
    justifyContent: "flex-start",
  },
  avatarMini: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: doctorPalette.surfaceLime,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarMiniText: {
    fontSize: 14,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  rowName: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "800",
    color: doctorPalette.ink,
  },
  rowSub: {
    fontSize: 11,
    color: doctorPalette.muted,
  },
  rowUhid: {
    fontSize: typography.fontSize.bodySmall,
    fontWeight: "600",
    color: doctorPalette.ink,
  },
  rowDate: {
    fontSize: typography.fontSize.caption,
    color: doctorPalette.muted,
  },
});
