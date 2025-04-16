import { describe, expect, it } from "vitest";
import { InvalidParamError } from "../../src/presentation/errors/index.js";
import { PathSecurityValidator } from "../../src/validators/path-security-validator.js";

describe("PathSecurityValidator", () => {
  it("should return null if field is not provided", () => {
    const sut = new PathSecurityValidator("field");
    const input = {};
    const error = sut.validate(input);

    expect(error).toBeNull();
  });

  it("should return null if input is null", () => {
    const sut = new PathSecurityValidator("field");
    const error = sut.validate(null);

    expect(error).toBeNull();
  });

  it("should return null if input is undefined", () => {
    const sut = new PathSecurityValidator("field");
    const error = sut.validate(undefined);

    expect(error).toBeNull();
  });

  it("should return InvalidParamError if field contains directory traversal (..)", () => {
    const sut = new PathSecurityValidator("field");
    const input = { field: "something/../etc/passwd" };
    const error = sut.validate(input);

    expect(error).toBeInstanceOf(InvalidParamError);
    expect(error?.message).toBe(
      "Invalid parameter: field contains invalid path segments"
    );
  });

  it("should return InvalidParamError if field contains directory traversal (..) even without slashes", () => {
    const sut = new PathSecurityValidator("field");
    const input = { field: "something..etc" };
    const error = sut.validate(input);

    expect(error).toBeInstanceOf(InvalidParamError);
    expect(error?.message).toBe(
      "Invalid parameter: field contains invalid path segments"
    );
  });

  it("should return InvalidParamError if field contains forward slashes", () => {
    const sut = new PathSecurityValidator("field");
    const input = { field: "path/to/file" };
    const error = sut.validate(input);

    expect(error).toBeInstanceOf(InvalidParamError);
    expect(error?.message).toBe(
      "Invalid parameter: field contains invalid path segments"
    );
  });

  it("should return null if field is a valid string without path segments", () => {
    const sut = new PathSecurityValidator("field");
    const input = { field: "validname123" };
    const error = sut.validate(input);

    expect(error).toBeNull();
  });

  it("should return null if field contains periods but not double periods", () => {
    const sut = new PathSecurityValidator("field");
    const input = { field: "filename.txt" };
    const error = sut.validate(input);

    expect(error).toBeNull();
  });

  it("should ignore non-string fields", () => {
    const sut = new PathSecurityValidator("field");
    const input = { field: 123 as any };
    const error = sut.validate(input);

    expect(error).toBeNull();
  });
});
