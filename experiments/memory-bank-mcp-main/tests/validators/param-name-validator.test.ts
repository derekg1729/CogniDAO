import { describe, expect, it } from "vitest";
import { InvalidParamError } from "../../src/presentation/errors/index.js";
import { ParamNameValidator } from "../../src/validators/param-name-validator.js";

describe("ParamNameValidator", () => {
  it("should return null if field is not provided", () => {
    const sut = new ParamNameValidator("field");
    const input = {};
    const error = sut.validate(input);

    expect(error).toBeNull();
  });

  it("should return null if input is null", () => {
    const sut = new ParamNameValidator("field");
    const error = sut.validate(null);

    expect(error).toBeNull();
  });

  it("should return null if input is undefined", () => {
    const sut = new ParamNameValidator("field");
    const error = sut.validate(undefined);

    expect(error).toBeNull();
  });

  it("should return InvalidParamError if field doesn't match regex (contains special characters)", () => {
    const sut = new ParamNameValidator("field");
    const input = { field: "invalid/name" };
    const error = sut.validate(input);

    expect(error).toBeInstanceOf(InvalidParamError);
    expect(error?.message).toBe("Invalid parameter: invalid/name");
  });

  it("should return InvalidParamError if field doesn't match regex (contains spaces)", () => {
    const sut = new ParamNameValidator("field");
    const input = { field: "invalid name" };
    const error = sut.validate(input);

    expect(error).toBeInstanceOf(InvalidParamError);
    expect(error?.message).toBe("Invalid parameter: invalid name");
  });

  it("should return null if field matches NAME_REGEX (alphanumeric only)", () => {
    const sut = new ParamNameValidator("field");
    const input = { field: "validname123" };
    const error = sut.validate(input);

    expect(error).toBeNull();
  });

  it("should return null if field matches NAME_REGEX (with underscores)", () => {
    const sut = new ParamNameValidator("field");
    const input = { field: "valid_name_123" };
    const error = sut.validate(input);

    expect(error).toBeNull();
  });

  it("should return null if field matches NAME_REGEX (with hyphens)", () => {
    const sut = new ParamNameValidator("field");
    const input = { field: "valid-name-123" };
    const error = sut.validate(input);

    expect(error).toBeNull();
  });

  it("should use provided regex instead of default NAME_REGEX if given", () => {
    // Custom regex that only allows lowercase letters
    const customRegex = /^[a-z]+$/;
    const sut = new ParamNameValidator("field", customRegex);

    const validInput = { field: "validname" };
    const validError = sut.validate(validInput);
    expect(validError).toBeNull();

    const invalidInput = { field: "Invalid123" };
    const invalidError = sut.validate(invalidInput);
    expect(invalidError).toBeInstanceOf(InvalidParamError);
  });
});
