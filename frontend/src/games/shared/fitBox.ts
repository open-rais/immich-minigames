export interface Size {
  width: number
  height: number
}

export interface Box {
  left: number
  top: number
  width: number
  height: number
}

// The object-contain "fit box": where an image's actual pixels render within its container,
// excluding letterbox padding - standard object-contain-fit math.
export function fitBox(natural: Size, container: Size): Box {
  const scale = Math.min(container.width / natural.width, container.height / natural.height)
  const width = natural.width * scale
  const height = natural.height * scale
  return {
    left: (container.width - width) / 2,
    top: (container.height - height) / 2,
    width,
    height,
  }
}
