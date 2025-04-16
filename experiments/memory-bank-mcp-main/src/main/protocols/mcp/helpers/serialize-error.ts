interface SerializedError {
  name: string;
  error: string;
  stack?: string;
  cause?: string | SerializedError;
  code?: string | number;
}

export const serializeError = (
  error: unknown,
  includeStack = false
): SerializedError => {
  if (error instanceof Error) {
    const serialized: SerializedError = {
      name: error.name,
      error: error.message,
    };

    if (includeStack) {
      serialized.stack = error.stack;
    }

    if ("cause" in error && error.cause) {
      serialized.cause =
        error.cause instanceof Error
          ? serializeError(error.cause, includeStack)
          : String(error.cause);
    }

    if (
      "code" in error &&
      (typeof error.code === "string" || typeof error.code === "number")
    ) {
      serialized.code = error.code;
    }

    return serialized;
  }

  return {
    name: "UnknownError",
    error: String(error),
  };
};
