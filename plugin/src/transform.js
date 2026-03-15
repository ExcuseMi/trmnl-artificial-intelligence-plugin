function transform(input) {
  const labels = {
    'llms':           'LLMs',
    'text-to-image':  'Text to Image',
    'text-to-speech': 'Text to Speech',
    'text-to-video':  'Text to Video',
    'image-to-video': 'Image to Video',
    'image-editing':  'Image Editing',
  };

  return {
    data: {
      ...input.data,
      labels,
      fetched_at: new Date().toISOString(),
    },
  };
}
