import { describe, expect, it, vi } from "vitest";
import { ReadRequest } from "../../../../src/presentation/controllers/read/protocols.js";
import { ReadController } from "../../../../src/presentation/controllers/read/read-controller.js";
import {
  NotFoundError,
  UnexpectedError,
} from "../../../../src/presentation/errors/index.js";
import { makeReadFileUseCase, makeValidator } from "../../mocks/index.js";

const makeSut = () => {
  const validatorStub = makeValidator<ReadRequest>();
  const readFileUseCaseStub = makeReadFileUseCase();
  const sut = new ReadController(readFileUseCaseStub, validatorStub);
  return {
    sut,
    validatorStub,
    readFileUseCaseStub,
  };
};

describe("ReadController", () => {
  it("should call validator with correct values", async () => {
    const { sut, validatorStub } = makeSut();
    const validateSpy = vi.spyOn(validatorStub, "validate");
    const request = {
      body: {
        projectName: "any_project",
        fileName: "any_file",
      },
    };
    await sut.handle(request);
    expect(validateSpy).toHaveBeenCalledWith(request.body);
  });

  it("should return 400 if validator returns an error", async () => {
    const { sut, validatorStub } = makeSut();
    vi.spyOn(validatorStub, "validate").mockReturnValueOnce(
      new Error("any_error")
    );
    const request = {
      body: {
        projectName: "any_project",
        fileName: "any_file",
      },
    };
    const response = await sut.handle(request);
    expect(response).toEqual({
      statusCode: 400,
      body: new Error("any_error"),
    });
  });

  it("should call ReadFileUseCase with correct values", async () => {
    const { sut, readFileUseCaseStub } = makeSut();
    const readFileSpy = vi.spyOn(readFileUseCaseStub, "readFile");
    const request = {
      body: {
        projectName: "any_project",
        fileName: "any_file",
      },
    };
    await sut.handle(request);
    expect(readFileSpy).toHaveBeenCalledWith({
      projectName: "any_project",
      fileName: "any_file",
    });
  });

  it("should return 404 if ReadFileUseCase returns null", async () => {
    const { sut, readFileUseCaseStub } = makeSut();
    vi.spyOn(readFileUseCaseStub, "readFile").mockResolvedValueOnce(null);
    const request = {
      body: {
        projectName: "any_project",
        fileName: "any_file",
      },
    };
    const response = await sut.handle(request);
    expect(response).toEqual({
      statusCode: 404,
      body: new NotFoundError("any_file"),
    });
  });

  it("should return 500 if ReadFileUseCase throws", async () => {
    const { sut, readFileUseCaseStub } = makeSut();
    vi.spyOn(readFileUseCaseStub, "readFile").mockRejectedValueOnce(
      new Error("any_error")
    );
    const request = {
      body: {
        projectName: "any_project",
        fileName: "any_file",
      },
    };
    const response = await sut.handle(request);
    expect(response).toEqual({
      statusCode: 500,
      body: new UnexpectedError(new Error("any_error")),
    });
  });

  it("should return 200 if valid data is provided", async () => {
    const { sut } = makeSut();
    const request = {
      body: {
        projectName: "any_project",
        fileName: "any_file",
      },
    };
    const response = await sut.handle(request);
    expect(response).toEqual({
      statusCode: 200,
      body: "file content",
    });
  });
});
