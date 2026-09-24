import React, { useMemo } from "react";
import { View, type ViewStyle } from "react-native";
import { buildQrMatrix } from "../doctorQr";

export type QrCodeViewProps = {
  value: string;
  size?: number;
  color?: string;
  backgroundColor?: string;
  quietZone?: number;
  testID?: string;
};

export function QrCodeView({
  value,
  size = 208,
  color = "#0F172A",
  backgroundColor = "#FFFFFF",
  quietZone = 0,
  testID,
}: QrCodeViewProps) {
  const matrix = useMemo(() => buildQrMatrix(value), [value]);

  const wrapperSize = size + quietZone * 2;
  const moduleSize = size / matrix.size;

  const innerStyle: ViewStyle = {
    position: "relative",
    width: size,
    height: size,
    left: quietZone,
    top: quietZone,
  };

  return (
    <View
      testID={testID}
      accessibilityLabel="QR code"
      style={{ width: wrapperSize, height: wrapperSize, backgroundColor }}
    >
      <View style={innerStyle}>
        {matrix.dark.map((cell, index) => (
          <View
            key={index}
            style={{
              position: "absolute",
              left: cell.col * moduleSize,
              top: cell.row * moduleSize,
              width: moduleSize,
              height: moduleSize,
              backgroundColor: color,
            }}
          />
        ))}
      </View>
    </View>
  );
}