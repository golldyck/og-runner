const fs = require('fs')
const path = require('path')

function writeVarint(n) {
  const out = []
  while (n > 127) {
    out.push((n & 0x7f) | 0x80)
    n >>= 7
  }
  out.push(n)
  return out
}

function writeLen(field, bytes) {
  return [(field << 3) | 2, ...writeVarint(bytes.length), ...bytes]
}

function writeString(field, str) {
  return writeLen(field, Array.from(new TextEncoder().encode(str)))
}

function writeInt64Field(field, val) {
  return [(field << 3) | 0, ...writeVarint(val)]
}

function dimProto(val) {
  return writeLen(1, writeInt64Field(1, val))
}

function shapeProto(...dims) {
  return writeLen(2, dims.flatMap((d) => writeLen(1, dimProto(d))))
}

function typeProto(shape) {
  return writeLen(1, [
    ...writeLen(1, [
      ...writeInt64Field(1, 1),
      ...shape,
    ]),
  ])
}

function valueInfo(name, ...dims) {
  return writeLen(1, [
    ...writeString(1, name),
    ...typeProto(shapeProto(...dims)),
  ])
}

function buildONNX(inputName, outputName, numFeatures) {
  const node1 = writeLen(1, [
    ...writeString(1, inputName),
    ...writeString(2, 'mid1'),
    ...writeString(3, 'relu1'),
    ...writeString(4, 'Relu'),
  ])

  const node2 = writeLen(1, [
    ...writeString(1, 'mid1'),
    ...writeString(2, 'mid2'),
    ...writeString(3, 'rs1'),
    ...writeString(4, 'ReduceSum'),
    ...writeLen(4, [
      ...writeString(1, 'axes'),
      ...writeInt64Field(2, 7),
      ...writeInt64Field(7, 1),
    ]),
    ...writeLen(4, [
      ...writeString(1, 'keepdims'),
      ...writeInt64Field(2, 1),
      ...writeInt64Field(4, 1),
    ]),
  ])

  const node3 = writeLen(1, [
    ...writeString(1, 'mid2'),
    ...writeString(2, outputName),
    ...writeString(3, 'relu2'),
    ...writeString(4, 'Relu'),
  ])

  const graph = [
    ...node1,
    ...node2,
    ...node3,
    ...writeString(2, 'dex_liquidity_exit_graph'),
    ...valueInfo(inputName, 1, numFeatures),
    ...valueInfo(outputName, 1, 1),
  ]

  const graphProto = writeLen(7, graph)
  const model = [
    ...writeInt64Field(1, 7),
    ...writeInt64Field(5, 9),
    ...writeString(2, 'dex-liquidity-exit-risk-scorer'),
    ...graphProto,
  ]

  return new Uint8Array(model)
}

const outputPath = path.join(__dirname, 'dex-liquidity-exit-risk-scorer.onnx')
const bytes = buildONNX('features', 'liquidity_exit_risk_score', 24)
fs.writeFileSync(outputPath, bytes)
console.log(`Wrote ${outputPath}`)
