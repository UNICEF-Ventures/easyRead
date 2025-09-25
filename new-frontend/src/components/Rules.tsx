import {
    Modal,
    ModalContent,
    ModalHeader,
    ModalBody,
    ModalFooter,
    Button,
    useDisclosure,
} from "@heroui/react";

export default function Rules({ isOpen, onOpen, onOpenChange }) {

    return (
        <Modal isOpen={isOpen} onOpenChange={onOpenChange} className="rounded-none" placement="top-center" classNames={{
            base:"mt-20 md:mt-10"
        }}>
            <ModalContent>
                {(onClose) => (
                    <>
                        <ModalHeader className="rounded-none flex flex-col gap-1 bg-gray-100">Rules for Play</ModalHeader>
                        <ModalBody className=" py-6 px-6">
                            <p> You are eligible for 15 monthly requests using this tool. It is an experimental model for testing and the outputs would require human review.
                            </p>
                            <p>
                                We may monitor and track your use for feedback, and follow up with a survey on your experience.
                            </p>
                            <p className="text-danger">
                                This tool is not for programmatic use.
                            </p>

                        </ModalBody>
                        <ModalFooter className="flex p-0 gap-0 justify-center items-center bg-gray-100">
                            <Button className="bg-primary text-secondary w-[50%] border-r-1 rounded-none p-6" onPress={onClose}>
                                Agree
                            </Button>
                            <Button className="bg-transparent w-[50%] text-black rounded-none p-6" onPress={onClose}>
                                Learn More
                            </Button>
                        </ModalFooter>
                    </>
                )}
            </ModalContent>
        </Modal>
    );
}
